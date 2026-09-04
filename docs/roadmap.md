# Roadmap

Meilensteine und **ehrlicher** Umsetzungsstand. Der Status wird gegen den tatsächlichen Code
geprüft, nicht gegen die Absicht. Was hier „fertig" heißt, muss laufen.

## Status-Werte

`offen` · `in Arbeit` · `fertig` · `zurückgestellt`

## Meilensteine

## Offen, unabhängig von den Meilensteinen

| Punkt | Status | Verweis |
|---|---|---|
| Lizenz festlegen | fertig | [README.md](../README.md), [LICENSE](../LICENSE) |

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
Modbus-Automation (`script.venus_e_1_steuerung`, live in der Zielanlage beobachtet — aufgerufen
aus `script.hems_postskript`).

**Status: in Arbeit.** Die eingebaute HEMS-Anbindung (`hems_bridge.py`, D-009) ist fertig und
getestet. Die Inbetriebnahme an der echten Anlage läuft (Schritte 1, 2 und 5 sind seit
03.09.2026 erledigt — Entry „AC Speicher 1" mit HEMS-Präfix `acspeicher1` läuft produktiv),
dabei kam Schritt 3 aber ins Stocken (siehe [bekannte-luecken.md](bekannte-luecken.md), Abschnitt
„An echter Venus E 3.0 beobachtet") und deckte zusätzlich einen Nebenläufigkeits-Bug auf, der
Schritt 4 bislang verfälscht hat. Reihenfolge ist bindend, jeder Schritt setzt den vorherigen
voraus. Schritte mit „manuell, überwacht" sind bewusst kein Automatismus — die
Hardware-Verifikation macht der User selbst an der echten Anlage.

| # | Schritt | Status | Verweis |
|---|---|---|---|
| 1 | Integration deployen: HACS custom repository `NicoHackl/Skytech-HEMS-Battery-Provider` oder manuell nach `custom_components/battery_bridge` kopieren, HA neu starten | fertig (03.09.2026) | [README.md](../README.md) |
| 2 | Config-Entry für den Marstek-Speicher anlegen (Einstellungen → Geräte & Dienste), Host/Port eintragen, HEMS-Präfix-Feld zunächst **leer lassen** — Verbindungstest läuft automatisch | fertig (03.09.2026) | |
| 3 | **Manuell, überwacht:** Lese-Werte (SoC, Ist-Lade-/Entladeleistung) über eine volle Lade-/Entlade-/Standby-Phase gegen die bisherigen Sensoren plausibilisieren, insbesondere `bat_power`-Vorzeichen bestätigen | in Arbeit — SoC bestätigt (plausibel); `bat_power` fehlt weiterhin, Ersatzwert über `ongrid_power` seit 0.2.1 im Einsatz (Vorzeichen von Nutzer-Beobachtung übernommen, weiterhin nicht offiziell bestätigt) | [bekannte-luecken.md](bekannte-luecken.md) |
| 4 | **Manuell, überwacht:** Schreibtest mit kleinem Sollwert (z. B. 100 W) auf `number.<prefix>_soll_ladeleistung`/`_soll_entladeleistung`, Reaktion am Gerät/in der Marstek-App beobachten, danach zurück auf 0 | in Arbeit — Anlage lief bereits unter aktiver HEMS-Steuerung (Präfix eingetragen), dabei sichtbares Dauer-Springen der Leistung gemeldet und auf einen Zero-Sollwert-Bug in `hems_bridge.py` zurückgeführt (behoben, 0.2.1) — Deploy dieses Fixes an der echten Anlage steht noch aus | [bekannte-luecken.md](bekannte-luecken.md) |
| 5 | Im Config-Entry das HEMS-Präfix eintragen (z. B. `acspeicher1`) — ab hier übersetzt `hems_bridge.py` selbst laufend, keine weitere Einrichtung nötig | fertig (03.09.2026) | [api-referenz.md](api-referenz.md) |
| 6 | HEMS-Gerätekonfiguration (im HEMS-Repo) auf die neuen Sensor-Entities umstellen | offen, **blockiert**: die tatsächlich live verwendeten Sensor-Entity-IDs für `acspeicher1` sind unbekannt — nicht raten, vor diesem Schritt am System klären | |
| 7 | Bewährungsphase im Normalbetrieb (Dauer: User legt fest); `script.venus_e_1_steuerung` dabei nur aus dem `parallel`-Block von `script.hems_postskript` entfernen, nicht löschen (schneller Rollback bleibt möglich) | offen | |
| 8 | Nach ausdrücklicher Freigabe: alte Modbus-Automation/-Integration entfernen | offen | |

## Zurückgestellt

| Thema | Warum zurückgestellt | Bedingung für Wiederaufnahme |
|---|---|---|
| Weitere Hersteller/Protokolle (Modbus TCP, HTTP/REST, MQTT) | Marstek UDP ist der einzige aktuell benötigte Adapter | Marstek-Adapter stabil in Betrieb **und** konkreter Bedarf für einen zweiten Hersteller/Speicher |
| Geräte-Discovery per UDP-Broadcast (`Marstek.GetDevice`) im Config-Flow | Komfortfeature (plan.md Abschnitt 5) — manuelle IP-Eingabe im Config-Flow funktioniert bereits | Konkretes Nutzerfeedback, dass manuelle IP-Eingabe stört |

---

Beschlossen, aber noch nicht gebaut → hier mit Status `offen`.
Gebaut, aber abweichend von der Doku → [bekannte-luecken.md](bekannte-luecken.md).
Warum so entschieden → [design-entscheidungen.md](design-entscheidungen.md).
