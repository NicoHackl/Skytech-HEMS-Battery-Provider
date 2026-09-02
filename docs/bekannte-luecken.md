# Bekannte Lücken und Stolpersteine

**Vor jeder Annahme lesen.** Diese Datei existiert, weil Doku und Code auseinanderlaufen. Steht
etwas in [architektur.md](architektur.md), heißt das nicht, dass es implementiert ist — hier steht,
wo nicht.

## Abweichungen Spec ↔ Code

Noch keine — Projekt ist im Scaffold-Stand, es existiert noch kein Adapter-Code
(siehe [roadmap.md](roadmap.md) M1).

## Vor der Marstek-Implementierung zu klären

Aus [plan.md](../plan.md) Abschnitt 5 — nicht raten, aus der offiziellen Doku entnehmen:

| Frage | Betrifft | Blockiert |
|---|---|---|
| Exakte Methodennamen/Payload für SoC- und Leistungsabfrage | `adapters/marstek_udp.py: read()` | M1 |
| Exakte Methodennamen/Payload zum Setzen einer Lade-/Entladeleistungsvorgabe | `adapters/marstek_udp.py: write_*()` | M2 |
| Nimmt die Venus E 3.0 über UDP einen direkten Leistungs-Sollwert (Watt) entgegen, oder nur einen Betriebsmodus („Manual Mode" + festes Zielfenster)? | `number.py`, ob stufenlos oder Moduskonzept nötig | M2 |
| Tatsächliche Reaktionszeit auf eine geschriebene Leistungsvorgabe (bekannt ist nur „~3 s" für Selbstverbrauchsmodus mit CT002, nicht für eine direkte Vorgabe) | Poll-Intervall in `coordinator.py` | M2 |

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
