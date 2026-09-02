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

## Stolpersteine

Dinge, die schon einmal Zeit gekostet haben:

- Noch keine — Projekt ist im Scaffold-Stand.

## Offene Bugs

Noch keine — es existiert noch kein lauffähiger Code.

## Bewusst nicht umgesetzt

| Thema | Warum nicht | Verweis |
|---|---|---|
| Weitere Hersteller/Protokolle (Modbus TCP, HTTP/REST, MQTT) | Kein aktueller Bedarf, Marstek UDP deckt den Start | D-006, [roadmap.md](roadmap.md) |
| „Bridge"-Baustein, der HEMS-Anforderungshelfer direkt übersetzt | Würde die HEMS-Architekturgrenze verwischen | D-005, [roadmap.md](roadmap.md) |

---

Wird ein Punkt behoben, wird er hier **gelöscht** und im [CHANGELOG.md](../CHANGELOG.md) vermerkt.
Eine Liste voller erledigter Einträge liest niemand mehr.
