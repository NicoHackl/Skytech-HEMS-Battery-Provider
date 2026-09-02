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

| Punkt | Status | Verweis |
|---|---|---|
| Marstek Open-API-Doku vollständig lesen, exakte Read-Commands festhalten | offen | |
| Repo-Grundgerüst (Abschnitt 3 in [plan.md](../plan.md)) | offen | |
| `StorageAdapter`-Protocol + `models.py` | offen | |
| `adapters/marstek_udp.py`: `connect()`/`read()`/`close()` | offen | |
| `coordinator.py`, `config_flow.py` (mit Verbindungstest) | offen | |
| `sensor.py` | offen | |

### M2 — Schreibzugriff (Soll-Leistung)

**Ziel:** `number.*`-Entities setzen tatsächlich eine Lade-/Entladeleistung auf dem Speicher.

| Punkt | Status | Verweis |
|---|---|---|
| Klärung: direkter Leistungssollwert oder nur Betriebsmodus? (siehe [bekannte-luecken.md](bekannte-luecken.md)) | offen | |
| `write_charge_power()`/`write_discharge_power()` im Adapter | offen | |
| `number.py` | offen | |
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
| Optionaler „Bridge"-Baustein, der die HEMS-Anforderungshelfer direkt übersetzt | Bewusst nicht Teil dieser Integration, um die HEMS-Grenze („kein direktes Schalten") nicht zu verwischen | Explizite Design-Entscheidung, falls die schlanke HA-Automation aus Abschnitt 9 in [plan.md](../plan.md) nicht ausreicht |

---

Beschlossen, aber noch nicht gebaut → hier mit Status `offen`.
Gebaut, aber abweichend von der Doku → [bekannte-luecken.md](bekannte-luecken.md).
Warum so entschieden → [design-entscheidungen.md](design-entscheidungen.md).
