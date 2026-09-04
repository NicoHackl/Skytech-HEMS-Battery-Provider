# D-011: Schalter pausiert/setzt HEMS-Anbindung fort, steht nach Neustart immer auf EIN

- **Datum:** 04.09.2026
- **Status:** Aktiv
- **Betrifft:** `switch.py` (neu), `hems_bridge.py`, `__init__.py`, `strings.json`/`translations/de.json`

## Kontext

Solange eine HEMS-Anbindung für einen Speicher aktiv ist, überschreibt `hems_bridge.py` laufend
jeden manuell über `number.<prefix>_soll_ladeleistung`/`_soll_entladeleistung` gesetzten Wert
beim nächsten HEMS-Zyklus wieder — dokumentiert in `bekannte-luecken.md`, seit D-010 auch über
`sensor.<prefix>_hems_soll_*` sichtbar, aber bis hierher nicht vermeidbar außer durch komplettes
Entfernen des HEMS-Präfixes im Config-Entry. Der User will gelegentlich selbst bestimmen können,
was der Speicher lädt/entlädt (z. B. für einen Test oder eine Sonderlage), ohne die HEMS-Anbindung
dafür dauerhaft abklemmen zu müssen — ausdrücklicher Wunsch nach einem Schalter unter der
„Konfiguration"-Rubrik der Geräteseite.

Eine zentrale Frage dabei: übersteht eine Pause einen HA-Neustart oder eine Neuinstallation der
Integration? Das ist keine reine Umsetzungsfrage, sondern ändert reales Sicherheitsverhalten —
deshalb ausdrücklich mit dem User abgestimmt, nicht selbst entschieden.

## Betrachtete Optionen

### Option A — Pause übersteht einen Neustart (`RestoreEntity`)

- Dafür: kein überraschendes automatisches Wiedereinschalten der HEMS-Steuerung, wenn der User
  bewusst pausiert hatte.
- Dagegen: wäre die erste Verwendung von `RestoreEntity`/`async_get_last_state` in diesem Repo —
  mehr Code, ein neuer Mechanismus. Vor allem aber: vergisst der User, dass er pausiert hatte, und
  startet HA aus einem völlig anderen Grund neu (Update, Stromausfall), bleibt der Speicher
  unbemerkt ohne jede automatische Steuerung — potenziell tagelang.

### Option B — Schalter steht nach jedem Neustart/Neuladen wieder auf EIN (gewählt)

- Dafür: folgt der einzigen bereits bestehenden Konvention dieses Projekts für Neustart-Verhalten
  (`number.py` setzt seinen Sollwert ebenfalls immer auf `0.0` zurück, kein `RestoreEntity`
  irgendwo im Repo) und der „HEMS im Zweifel vertrauen"-Sicherheitslogik, die `hems_bridge.py`
  für `_MODE_LADEN`/`_MODE_ENTLADEN` ohnehin schon anwendet (unbekannter Wert → sicherer Fall).
  Kein neuer Persistenzmechanismus nötig.
- Dagegen: eine bewusste Pause für einen längeren manuellen Eingriff muss der User nach jedem
  Neustart aktiv wiederherstellen.

## Entscheidung

Option B, mit dem User ausdrücklich abgestimmt. `HemsBridge._enabled` ist ein einfaches
Instanzattribut, startet immer `True` in `__init__`. `switch.<prefix>_hems_steuerung_aktiv`
(`entity_category=CONFIG`, erste Verwendung von `EntityCategory` in diesem Repo) spiegelt es über
`is_on`/`async_turn_on`/`async_turn_off`. Ausgeschaltet überspringt `_async_sync()` ganz am Anfang
jeden Sync (keine Helfer-Abfrage, keine Adapter-Schreibaufrufe). Eingeschaltet synchronisiert
`async_resume()` sofort mit dem aktuellen HEMS-Sollwert, statt auf die nächste zufällige
Helfer-Änderung zu warten, und setzt zusätzlich `_last_applied_mode = None` zurück — erzwingt den
Zero-Schritt der inaktiven Richtung auch dann, wenn sich die HEMS-Betriebsart seit der Pause nicht
geändert hat, falls während der Pause manuell an `number.*_soll_*` gedreht wurde.

`switch.py` ändert nie selbst einen Geräte-Sollwert (Invariante 5, `architektur.md`) — er schaltet
ausschließlich, ob `hems_bridge.py` automatisch schreibt.

## Folgen

- **Positiv:** Der User kann `number.<prefix>_soll_*` gefahrlos selbst bedienen, ohne HEMS-Bezug
  zum Speicher dauerhaft zu entfernen. Kein neuer Persistenzmechanismus, kein Widerspruch zum
  Nicht-Ziel „keine eigene Persistenz" (`architektur.md`).
- **Negativ:** Eine bewusste, länger geplante Pause übersteht keinen Neustart — der User muss sie
  nach jedem Neustart aktiv erneut setzen.
- **Aufwand:** `enabled`/`async_pause()`/`async_resume()` in `hems_bridge.py`, neues Modul
  `switch.py`, `Platform.SWITCH` in `PLATFORMS`, neue Übersetzung, sechs neue Tests
  (`test_hems_bridge.py` + `test_switch.py`).

## Rücknahmebedingung

Zeigt sich in der Praxis, dass Nutzer wiederholt vergessen, die Steuerung nach einem Neustart
erneut zu pausieren (z. B. weil ein Neustart mitten in einem längeren manuellen Eingriff passiert),
wäre eine sichtbarere Erinnerung (z. B. eine Warnung/ein Repair-Issue) oder doch `RestoreEntity`
zu erwägen — dann würde diese Entscheidung überarbeitet, nicht stillschweigend umgangen.
