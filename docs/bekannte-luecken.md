# Bekannte Lücken und Stolpersteine

**Vor jeder Annahme lesen.** Diese Datei existiert, weil Doku und Code auseinanderlaufen. Steht
etwas in [architektur.md](architektur.md), heißt das nicht, dass es implementiert ist — hier steht,
wo nicht.

## Abweichungen Spec ↔ Code

| Thema | Doku sagt | Code macht | Folge für die Arbeit |
|---|---|---|---|
| Python-Version | `plan.md` Abschnitt 2 nannte Python 3.11 | `pyproject.toml` verlangt `>=3.13` | Aktuelles HA-Core und `pytest-homeassistant-custom-component` (Stand 09/2026) setzen Python ≥3.13 voraus — bei `uv sync` löste die Auflösung mit `<3.14` sonst nicht auf. Reine Umsetzungsanpassung an die Laufzeit, keine bewusste Design-Entscheidung, siehe [architektur.md](architektur.md). |

## Vor dem produktiven Schreibzugriff (M2) zu bestätigen

Die Mechanismus-Frage ist geklärt (siehe „Marstek-Protokoll — Quellenlage" unten): Passive-Mode
ist implementiert. Offen bleibt nur noch die Praxisprobe an echter Hardware — **kein Sollwert
wird ungeprüft an eine echte Anlage gesendet**, bevor das hier abgehakt ist:

| Frage | Betrifft | Blockiert |
|---|---|---|
| Sendet `write_charge_power`/`write_discharge_power` das richtige Vorzeichen? (`power` negativ = laden, positiv = entladen, aus zwei Quellen übereinstimmend übernommen — siehe unten) | `adapters/marstek_udp.py: _set_passive_power()` | Produktiver Einsatz von M2 |
| Fällt das Gerät nach `cd_time` (300 s) tatsächlich in den vorherigen Modus zurück, wenn kein neuer Sollwert kommt? (Sicherheitsannahme, aus keiner Quelle explizit als Verhalten bestätigt, nur als Zweck des Parameters plausibel) | Verhalten bei einer hängenden/abgestürzten Integration | Produktiver Einsatz von M2 |
| Tatsächliche Reaktionszeit auf eine geschriebene Leistungsvorgabe (bekannt ist nur „~3 s" für Selbstverbrauchsmodus mit CT002, nicht für eine direkte Vorgabe) | Poll-Intervall in `coordinator.py` | M2, Feintuning |

## Marstek-Protokoll — Quellenlage

Marstek veröffentlicht die Local API nicht offiziell. Verwendet werden `Bat.GetStatus` (Feld
`soc`), `ES.GetStatus` (Felder `bat_soc`, `bat_power`) und `ES.SetMode` (Passive-Mode,
`passive_cfg: {power, cd_time}`) — zusammengetragen aus vier unabhängigen Community-Quellen:
[Randyocean/Marstek](https://github.com/Randyocean/Marstek/blob/main/docs/marstek_device_openapi.MD)
(Protokoll-Dump), [taurgis/has-marstek-local-api](https://github.com/taurgis/has-marstek-local-api),
[jaapp/ha-marstek-local-api](https://github.com/jaapp/ha-marstek-local-api) und
[leonscheltema/ha-marstek](https://github.com/leonscheltema/ha-marstek) — alle vier aktiv
gepflegt, Venus E 3.0 wird von mindestens taurgis ausdrücklich als unterstützt genannt
(Venus E2.0 ausdrücklich **nicht**).

**Lesepfad (`bat_power`) — Vorzeichenkonvention unverifiziert:** Randyocean dokumentiert
„positiv = entladen", der tatsächliche Code von taurgis liest das Gegenteil („positiv = laden")
und negiert es für die eigene Konvention. `adapters/marstek_udp.py` übernimmt die
taurgis-Lesart (aktiver, gepflegter Code wiegt schwerer als eine Doku-Kopie) — **vor dem
produktiven Einsatz an echter Hardware bestätigen** (Plan Abschnitt 5, Plan-Schritt 4): Speicher
laden lassen, prüfen, dass `sensor.<prefix>_ist_ladeleistung` und nicht
`..._ist_entladeleistung` den Wert zeigt.

**Schreibpfad (`ES.SetMode` Passive) — Mechanismus geklärt, Vorzeichen mit mittlerer
Zuversicht:** Alle vier Quellen setzen für einen direkten Leistungs-Sollwert übereinstimmend auf
Passive-Mode statt Manual-Mode (Manual ist für feste Tageszeitpläne). Für die Vorzeichenkonvention
des `power`-Felds stimmen jaapp und leonscheltema unabhängig überein: positiv = entladen, negativ
= laden — das deckt sich mit der (bereits negierten) HA-Anzeigekonvention aus dem Lesepfad, ist
aber nicht dieselbe Quelle wie der rohe `bat_power`-Wert und **ebenfalls nicht an echter Hardware
verifiziert**. Ein falsches Vorzeichen hier ist folgenreicher als beim Lesepfad — ein Sollwert
steuert echte Leistung, ein Lesewert nur eine Anzeige. Deshalb: erster produktiver Testlauf mit
kleinem Sollwert (z. B. 100 W) und Blick auf die tatsächliche Reaktion des Speichers, nicht
direkt mit einem Sollwert, der etwas kaputt machen kann.

## An echter Venus E 3.0 beobachtet (03.09.2026)

Erster Praxiskontakt der Integration mit einer echten Anlage. SoC-Anzeige und ein erstes manuelles
Setzen der Soll-Lade-/Entladeleistung funktionierten; danach zwei Auffälligkeiten:

- **`ES.SetMode`-Aufrufe der HEMS-Anbindung timeoueten fast durchgehend, `ES.GetStatus`
  (Coordinator-Poll) nur gelegentlich.** Ursache gefunden und behoben: `MarstekUdpAdapter`
  teilte eine einzige Antwort-Queue zwischen allen `_call()`-Aufrufen, ohne sie zu
  serialisieren — der Coordinator-Poll (fester 5-s-Takt) und die HEMS-Anbindung (eigener Task,
  ausgelöst bei jeder Änderung der HEMS-Anforderungshelfer, damit im Sekundentakt) liefen auf
  demselben Adapter parallel. Traf die Antwort auf Anfrage A ein, während eine andere Anfrage B
  gerade in ihrer eigenen Warteschleife auf die Queue wartete, konnte B sie zuerst aus der Queue
  holen, an der ID als fremd erkennen und per `continue` verwerfen (nicht zurücklegen) — A bekam
  seine eigene, korrekte Antwort nie zugestellt und timeoutete, obwohl das Gerät geantwortet
  hatte. Da die HEMS-Anbindung viel häufiger sendet als der Poll, traf es `ES.SetMode` fast
  immer. Fix: `asyncio.Lock` in `adapters/marstek_udp.py`, serialisiert jetzt jeden
  Request-Antwort-Zyklus vollständig — Test `test_gleichzeitige_aufrufe_teilen_sich_nicht_die_antwort`.
- **Offen, weiterhin nicht geraten:** `sensor.<prefix>_ist_ladeleistung`/`_ist_entladeleistung`
  zeigten dauerhaft `unknown`, obwohl `sensor.<prefix>_ladezustand` (SoC) im selben Zeitraum
  gültige Werte aus demselben `ES.GetStatus`-Aufruf zeigte. `bat_power` ist laut
  Randyocean-Protokoll-Dump ein reguläres Feld dieser Antwort (Beispiel dort zeigt `bat_power: 0`
  im Leerlauf) — auf der echten Anlage fehlt es im Ergebnis aber anscheinend, obwohl `bat_soc` im
  selben Ergebnis vorhanden ist. Ob das am Firmwarestand der Venus E 3.0, an einem
  Anlagenzustand (z. B. Standby) oder an einer noch unbekannten dritten Ursache liegt, ist
  unklar — dafür fehlt die rohe Antwort. `read()` loggt eine fehlende `bat_power` deshalb jetzt
  auf Debug-Level mit der vollständigen Rohantwort (`adapters/marstek_udp.py`). **Nächster
  Schritt:** Log-Level für `custom_components.battery_bridge` auf `debug` stellen, eine Zeit
  über verschiedene Anlagenzustände (Laden/Entladen/Standby) laufen lassen, Rohantwort
  auswerten — erst danach hier eintragen, was tatsächlich der Fall ist.

## Stolpersteine

Dinge, die schon einmal Zeit gekostet haben:

- **`StorageAdapterError`-Meldungen sind für das Log geschrieben, nicht für den Nutzer.** Sie
  enthalten bewusst Host, Port, JSON-RPC-Methodennamen und rohe Antwort-Dicts (siehe
  `adapters/marstek_udp.py`) — wertvoll beim Debuggen, aber ein Verstoß gegen Regel 12, sobald sie
  unverändert in eine `HomeAssistantError` wandern. Genau das ist `number.py` passiert (siehe
  CHANGELOG.md). Ein künftiger zweiter Adapter (D-006) muss dasselbe Muster einhalten: technisch
  loggen, dann eine eigene Nutzermeldung bauen — nie `str(exc)` direkt an eine HA-Exception geben.

## Offene Bugs

Noch keine.

## Vor dem produktiven Einsatz der HEMS-Anbindung (`hems_bridge.py`) zu bestätigen

Dieselbe Vorsicht wie bei M2 (siehe oben) — die Übersetzungslogik selbst ist getestet, aber die
Schreibaufrufe, die sie auslöst, laufen über denselben unverifizierten Marstek-Schreibpfad:

| Frage | Betrifft | Blockiert |
|---|---|---|
| Löst ein Wechsel von `laden`/`entladen`/`standby` am Gerät tatsächlich die erwartete Richtung aus, in der von `hems_bridge.py` gewählten Reihenfolge (inaktiv zuerst auf 0)? | `hems_bridge.py: _async_sync()` | Aktivierung der HEMS-Anbindung an echter Hardware |
| Solange die HEMS-Anbindung für einen Entry aktiv ist, überschreibt sie laufend die eigenen `number.*_soll_*`-Entities — manuelles Bedienen dieser Entities in diesem Zustand wird vom nächsten HEMS-Zyklus (Sekundentakt) sofort wieder verworfen. | `number.py` vs. `hems_bridge.py` | Kein Bug, aber überraschend, wenn nicht dokumentiert |

## Bewusst nicht umgesetzt

| Thema | Warum nicht | Verweis |
|---|---|---|
| Weitere Hersteller/Protokolle (Modbus TCP, HTTP/REST, MQTT) | Kein aktueller Bedarf, Marstek UDP deckt den Start | D-006, [roadmap.md](roadmap.md) |

---

Wird ein Punkt behoben, wird er hier **gelöscht** und im [CHANGELOG.md](../CHANGELOG.md) vermerkt.
Eine Liste voller erledigter Einträge liest niemand mehr.
