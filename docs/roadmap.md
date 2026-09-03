# Roadmap

Meilensteine und **ehrlicher** Umsetzungsstand. Der Status wird gegen den tatsächlichen Code
geprüft, nicht gegen die Absicht. Was hier „fertig" heißt, muss laufen.

## Status-Werte

`offen` · `in Arbeit` · `fertig` · `zurückgestellt`

## Meilensteine

## Offen, unabhängig von den Meilensteinen

| Punkt | Status | Verweis |
|---|---|---|
| Lizenz festlegen | offen | [README.md](../README.md) |

### M1 — Lesezugriff auf einen Marstek-Speicher

**Ziel:** SoC, Ist-Lade- und Ist-Entladeleistung eines Marstek-Speichers erscheinen als
HA-Sensoren, sobald der Speicher im Config-Flow eingerichtet ist.

**Status: in Arbeit.** Code steht und ist getestet (14 Tests, `pytest` + `ruff check .` grün),
aber noch **nie gegen eine echte Venus E 3.0 gelaufen** — insbesondere die Vorzeichenkonvention
von `bat_power` ist unverifiziert (siehe [bekannte-luecken.md](bekannte-luecken.md)). Erst nach
diesem Praxistest gilt M1 als abgeschlossen (Plan Abschnitt 14, Schritt 4).

| Punkt | Status | Verweis |
|---|---|---|
| Marstek Open-API-Doku gelesen, Read-Commands festgehalten (`Bat.GetStatus`, `ES.GetStatus`) | fertig | [bekannte-luecken.md](bekannte-luecken.md) |
| Repo-Grundgerüst (Abschnitt 3 in [plan.md](../plan.md)) | fertig | |
| `StorageAdapter`-Protocol + `models.py` | fertig | |
| `adapters/marstek_udp.py`: `connect()`/`read()`/`close()`, getestet | fertig | |
| `coordinator.py`, `config_flow.py` (mit Verbindungstest), getestet | fertig | |
| `sensor.py` | fertig | |
| An echter Hardware bestätigen: Vorzeichenkonvention `bat_power`, Werte plausibel | offen | [bekannte-luecken.md](bekannte-luecken.md) |

### M2 — Schreibzugriff (Soll-Leistung)

**Ziel:** `number.*`-Entities setzen tatsächlich eine Lade-/Entladeleistung auf dem Speicher.

**Status: in Arbeit.** Code steht und ist getestet, aber wie M1 **noch nie gegen eine echte
Venus E 3.0 gelaufen** — bei einer Steuerung ist das riskanter als bei einer Anzeige, deshalb
zusätzlich: erster Testlauf mit kleinem Sollwert, nicht mit einem produktionsnahen Wert
(siehe [bekannte-luecken.md](bekannte-luecken.md)).

| Punkt | Status | Verweis |
|---|---|---|
| Klärung: Passive-Mode-Sollwert oder Manual-Mode-Zeitfenster? | fertig — Passive-Mode, D-008 | [design-entscheidungen.md](design-entscheidungen.md) |
| `write_charge_power()`/`write_discharge_power()` im Adapter, getestet | fertig | |
| `number.py` | fertig | |
| An echter Hardware bestätigen: Vorzeichen, Watchdog-Verhalten nach `cd_time` | offen | [bekannte-luecken.md](bekannte-luecken.md) |
| Reaktionszeit an echter Hardware messen, Poll-Intervall justieren | offen | |

### M3 — HEMS-Anbindung

**Ziel:** SkytechHEMS liest/schreibt über diese Integration statt über die bisherige
Modbus-Automation.

| Punkt | Status | Verweis |
|---|---|---|
| HEMS-Gerätekonfiguration (im HEMS-Repo) auf die neuen Entities umstellen | offen | |
| Alte Modbus-Automation ablösen | offen | |

## Zurückgestellt

| Thema | Warum zurückgestellt | Bedingung für Wiederaufnahme |
|---|---|---|
| Weitere Hersteller/Protokolle (Modbus TCP, HTTP/REST, MQTT) | Marstek UDP ist der einzige aktuell benötigte Adapter | Marstek-Adapter stabil in Betrieb **und** konkreter Bedarf für einen zweiten Hersteller/Speicher |
| Geräte-Discovery per UDP-Broadcast (`Marstek.GetDevice`) im Config-Flow | Komfortfeature (plan.md Abschnitt 5) — manuelle IP-Eingabe im Config-Flow funktioniert bereits | Konkretes Nutzerfeedback, dass manuelle IP-Eingabe stört |

---

Beschlossen, aber noch nicht gebaut → hier mit Status `offen`.
Gebaut, aber abweichend von der Doku → [bekannte-luecken.md](bekannte-luecken.md).
Warum so entschieden → [design-entscheidungen.md](design-entscheidungen.md).
