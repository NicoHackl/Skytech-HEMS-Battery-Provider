# Bekannte Lücken und Stolpersteine

**Vor jeder Annahme lesen.** Diese Datei existiert, weil Doku und Code auseinanderlaufen. Steht
etwas in [architektur.md](architektur.md), heißt das nicht, dass es implementiert ist — hier steht,
wo nicht.

## Abweichungen Spec ↔ Code

| Thema | Doku sagt | Code macht | Folge für die Arbeit |
|---|---|---|---|
| Python-Version | `plan.md` Abschnitt 2 nannte Python 3.11 | `pyproject.toml` verlangt `>=3.13` | Aktuelles HA-Core und `pytest-homeassistant-custom-component` (Stand 09/2026) setzen Python ≥3.13 voraus — bei `uv sync` löste die Auflösung mit `<3.14` sonst nicht auf. Reine Umsetzungsanpassung an die Laufzeit, keine bewusste Design-Entscheidung, siehe [architektur.md](architektur.md). |

## Vor dem Schreibzugriff (M2) zu klären

Lesezugriff (M1) ist geklärt: `Bat.GetStatus`/`ES.GetStatus` sind bestätigte, aktiv verwendete
Methoden (siehe unten „Marstek-Protokoll — Quellenlage"). Offen bleibt nur der Schreibpfad:

| Frage | Betrifft | Blockiert |
|---|---|---|
| Passive-Mode (`ES.SetMode`, `passive_cfg: {power, cd_time}`, laut Randyocean-Doku ein direkter Watt-Sollwert mit Countdown-Watchdog) oder Manual-Mode (`manual_cfg` mit Zeitfenster, das taurgis/has-marstek-local-api tatsächlich verwendet) — welcher Weg funktioniert auf der Venus E 3.0 zuverlässig als Sollwert? | `adapters/marstek_udp.py: write_charge_power()/write_discharge_power()` | M2 |
| Tatsächliche Reaktionszeit auf eine geschriebene Leistungsvorgabe (bekannt ist nur „~3 s" für Selbstverbrauchsmodus mit CT002, nicht für eine direkte Vorgabe) | Poll-Intervall in `coordinator.py` | M2 |

## Marstek-Protokoll — Quellenlage (M1, Lesezugriff)

Marstek veröffentlicht die Local API nicht offiziell. Verwendet werden `Bat.GetStatus` (Feld
`soc`) und `ES.GetStatus` (Felder `bat_soc`, `bat_power`) — Methodennamen und Feldnamen sind über
zwei unabhängige Community-Quellen bestätigt:
[Randyocean/Marstek](https://github.com/Randyocean/Marstek/blob/main/docs/marstek_device_openapi.MD)
(Protokoll-Dump) und
[taurgis/has-marstek-local-api](https://github.com/taurgis/has-marstek-local-api) (aktiv
gepflegte HA-Integration, Venus E 3.0 ausdrücklich unterstützt).

**Unverifiziert bleibt die Vorzeichenkonvention von `bat_power`:** Randyocean dokumentiert
„positiv = entladen", der tatsächliche Code von taurgis liest das Gegenteil („positiv = laden")
und negiert es für die eigene Konvention. `adapters/marstek_udp.py` übernimmt die
taurgis-Lesart (aktiver, gepflegter Code wiegt schwerer als eine Doku-Kopie), macht das aber nur
für den Split in `charge_power_w`/`discharge_power_w` — **vor dem produktiven Einsatz an echter
Hardware bestätigen** (Plan Abschnitt 5, Plan-Schritt 4): Speicher laden lassen, prüfen, dass
`sensor.<prefix>_ist_ladeleistung` und nicht `..._ist_entladeleistung` den Wert zeigt.

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
