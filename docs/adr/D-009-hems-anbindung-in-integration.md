# D-009: HEMS-Anbindung wird Teil der Integration, nicht einer externen HA-Automation

- **Datum:** 03.09.2026
- **Status:** Aktiv
- **Betrifft:** `hems_bridge.py` (neu), `config_flow.py`, `const.py`, `coordinator.py`, `__init__.py`

## Kontext

`plan.md` §9 und die davon abgeleiteten `roadmap.md`/`bekannte-luecken.md`-Einträge gingen bisher
davon aus, dass die Übersetzung von HEMS' Anforderungsvertrag
(`input_number.ems_<prefix>_anforderung_leistung_w` signiert,
`input_select.ems_<prefix>_anforderung_betriebsart`) in die eigenen
`number.<prefix>_soll_ladeleistung`/`_soll_entladeleistung`-Entities außerhalb dieser Integration
passiert — eine schlanke, von Hand gepflegte HA-Automation, analog zum bisherigen
`script.venus_e_1_steuerung` (Modbus-Variante, live in der Zielanlage beobachtet). Ein optionaler
„Bridge"-Baustein in der Integration selbst war ausdrücklich zurückgestellt
(`roadmap.md`: „Bewusst nicht Teil dieser Integration, um die HEMS-Grenze nicht zu verwischen").

Der User hat diese Prämisse beim Arbeitspaket zur M3-Vorbereitung explizit zurückgewiesen: das
Projekt heißt „Skytech HEMS Battery Provider" und soll die **vollständige** Schnittstelle
zwischen HEMS und Speicher sein — nicht nur ein Entity-Lieferant, den man zusätzlich von Hand mit
einer YAML-Automation verkabeln muss, die bei jedem neuen Speicher erneut kopiert und angepasst
werden müsste.

## Betrachtete Optionen

### Option A — Externe HA-Automation (ursprünglicher Plan)

- Dafür: hält die Integration strikt "dumm" (reiner Entity-Lieferant), keine zusätzliche
  Laufzeit-Komponente, kein neues Config-Flow-Feld.
- Dagegen: von Hand in YAML gepflegt, pro Speicher erneut einzurichten, die
  Zwei-Setpoint-Reihenfolge (siehe Folgen unten) ist in YAML fehleranfälliger als in getestetem
  Python. Entspricht nicht dem vom User gewünschten Projektzweck.

### Option B — Eingebaute, optionale HEMS-Anbindung (gewählt)

- Dafür: die Integration ist tatsächlich die vollständige Schnittstelle, keine externe Automation
  nötig, die kritische Aufrufreihenfolge ist getestet statt handgepflegt, pro Config-Entry
  optional aktivierbar (Feld leer = unverändertes Verhalten als reiner Entity-Lieferant).
- Dagegen: koppelt die Integration an HEMS' Namenskonvention (`ems_<prefix>_anforderung_*`) für
  wer die Anbindung nutzt — bleibt aber optional, ändert nichts für Nutzung ohne HEMS.

## Entscheidung

Option B. Ein Config-Entry kann optional ein `hems_entity_prefix` hinterlegen; ist es gesetzt,
beobachtet `hems_bridge.py` die beiden HEMS-Helfer per `async_track_state_change_event` und ruft
bei jeder Änderung `adapter.write_charge_power()`/`write_discharge_power()` auf — in dieser
Reihenfolge zuerst die inaktive Richtung auf `0`, danach die aktive Richtung, weil
`write_charge_power`/`write_discharge_power` bei der Marstek-UDP-Anbindung keinen additiven
Zwei-Kanal-Sollwert steuern, sondern denselben einzigen Passive-Mode-Sollwert — der zuletzt
gesendete Aufruf gewinnt vollständig (siehe `adapters/marstek_udp.py`). Genau diese Falle wäre in
einer von Hand geschriebenen YAML-Automation leicht zu übersehen.

**D-005 bleibt unverändert gültig:** Keine Codeänderung in HEMS, weiterhin eine eigenständige
Integration statt einer HEMS-Erweiterung. D-009 ändert nur, **wo** die Übersetzung des
unveränderten HEMS-Vertrags stattfindet — nicht den Vertrag selbst, nicht die Architekturgrenze
(Invariante 4: diese Integration schaltet weiterhin ausschließlich ihre eigenen
Speicher-Entities).

## Folgen

- **Positiv:** Ein Speicher lässt sich vollständig über die HA-UI einrichten — Verbindungsdaten
  **und** HEMS-Anbindung in einem Schritt, keine zusätzliche, separat zu pflegende Automation.
  Die Zwei-Setpoint-Reihenfolge ist durch `tests/test_hems_bridge.py` abgesichert.
- **Negativ:** Die Integration kennt jetzt HEMS' Entity-Namensschema (`ems_<prefix>_anforderung_*`)
  — bleibt aber rein additiv/optional, ändert nichts an der Nutzung ohne HEMS-Präfix.
- **Aufwand:** Neues Modul `hems_bridge.py`, ein neues Config-Flow-Feld, ein neues
  Coordinator-Attribut (`hems_bridge`), acht neue Tests.

## Rücknahmebedingung

Zeigt sich in der Praxis, dass verschiedene HEMS-Installationen unterschiedliche
Übersetzungslogik bräuchten (z. B. andere Anforderungs-Kontrakte als
`anforderung_leistung_w`/`anforderung_betriebsart`), wäre eine generische, konfigurierbare
Übersetzung nötig statt der fest verdrahteten HEMS-Namenskonvention — dann würde diese
Entscheidung überarbeitet, nicht die Rückkehr zu Option A.
