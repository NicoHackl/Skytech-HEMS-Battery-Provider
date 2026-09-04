# D-012: HEMS-Anbindung sendet den Sollwert zusätzlich alle 60 s erneut (Keep-Alive)

- **Datum:** 04.09.2026
- **Status:** Aktiv — löst die Refresh-Annahme aus D-008 ab
- **Betrifft:** `hems_bridge.py`, `const.py`, `tests/test_hems_bridge.py`

## Kontext

D-008 legte den Schreibzugriff über `ES.SetMode` Passive-Mode fest und begründete `cd_time`
(300 s) als Sicherheits-Watchdog: sendet niemand mehr einen Sollwert, fällt das Gerät zurück in
den vorherigen Modus, statt einen Sollwert für immer zu erzwingen. D-008 ging dabei ausdrücklich
davon aus, dass kein automatischer Refresh-Loop nötig ist — „HEMS/Automationen senden bei Bedarf
selbst erneut".

`hems_bridge.py` ist rein ereignisgetrieben: `_async_sync()` läuft ausschließlich über
`async_track_state_change_event` auf die beiden HEMS-Anforderungshelfer
(`input_number.ems_<prefix>_anforderung_leistung_w`, `input_select.ems_<prefix>_anforderung_betriebsart`).
Ändert sich keiner der beiden Helferwerte, feuert HA kein `state_changed`-Event, und
`_async_sync()` läuft nicht erneut — unabhängig davon, wie lange der zuletzt gesendete Sollwert
schon gilt.

Am 04.09.2026 per `ha_get_history` (HA-Verlauf) rekonstruiert: An diesem Tag lud der Speicher
trotz laufender, unverändert bei 2500 W anliegender HEMS-Anforderung zweimal nicht mehr —
`sensor.<prefix>_hems_soll_ladeleistung` zeigte weiterhin den zuletzt erfolgreich gesendeten
Wert, `sensor.<prefix>_ist_ladeleistung` fiel auf 0 W. Beide Vorfälle lagen exakt ~300 s nach dem
letzten tatsächlich an den Adapter gesendeten Sollwert (13:37:08 → 13:42:12 = 304 s,
13:44:02 → 13:49:02 = 300 s) — deckt sich exakt mit `cd_time`. Kein Fehler im Log, weil kein
Schreibvorgang fehlgeschlagen ist: es wurde schlicht keiner mehr versucht, weil die HEMS-Helfer
in diesem Fenster wertkonstant blieben. Der User beobachtete das wiederholt, behelfsweise fixt
Aus-/Einschalten von `switch.<prefix>_hems_steuerung_aktiv` (`async_resume()`, D-011) — das
erzwingt einen sofortigen Sync unabhängig vom Event.

Damit ist die D-008-Annahme widerlegt: SkytechHEMS sendet nur bei tatsächlicher Wertänderung,
nicht periodisch. Der Watchdog verlangt aber einen neuen Aufruf unabhängig davon, ob sich der Wert
geändert hat — genau diese Lücke zwischen „Anforderung gilt weiter" und „Gerät braucht trotzdem
einen neuen Befehl" hat D-008 übersehen.

## Betrachtete Optionen

### Option A — Periodischer Keep-Alive-Resend (gewählt)

- Dafür: Einfacher, lokaler Fix in `hems_bridge.py` — ein zusätzlicher
  `async_track_time_interval`-Listener, der denselben `_async_sync()` erneut anstößt. Kein neuer
  Zustand, keine Änderung am bestehenden Event-Pfad oder an `mode_changed` — ein Keep-Alive-Tick
  ohne Wertänderung sendet die aktive Richtung erneut, ohne Zero-Zwischenschritt (siehe
  Moduldoc/D-009).
- Dagegen: Ein zusätzlicher, dauerhaft laufender Timer je Speicher mit HEMS-Präfix — minimal mehr
  Last auf dem seriellen `_call_lock` in `adapters/marstek_udp.py`, geteilt mit Coordinator-Poll
  und Event-Sync.

### Option B — `cd_time` selbst erhöhen (z. B. auf einen sehr hohen Wert)

- Dafür: Kein zusätzlicher Timer nötig.
- Dagegen: Untergräbt den Zweck des Watchdogs (D-008: „kein Sollwert bleibt für immer erzwungen,
  wenn HA nicht mehr antwortet") — ein abgestürztes/hängendes HA würde den letzten Sollwert dann
  entsprechend lange am Speicher erzwingen, statt zeitnah in einen sicheren Zustand
  zurückzufallen. Nicht verhandelbar bei einem Sicherheitsmechanismus.

### Option C — Coordinator-Poll (`read()`, 5-s-Takt) auch zum Resend nutzen

- Dafür: Kein zweiter Timer, ein bestehender Takt wird mitgenutzt.
- Dagegen: Vermischt zwei unabhängige Zuständigkeiten (Lesen vs. Schreiben) in einer Stelle, die
  bislang sauber getrennt sind (`coordinator.py` kennt `hems_bridge.py` nicht, nur umgekehrt) —
  und 5 s ist unnötig oft für einen reinen Watchdog-Refresh, mehr Last auf dem `_call_lock` ohne
  Nutzen.

## Entscheidung

Option A. Neue Konstante `HEMS_KEEPALIVE_INTERVAL` (`const.py`, 60 s — deutlich unter den 300 s
von `cd_time`, damit ein einzelner verpasster/verzögerter Tick keine kritische Lücke reißt, ohne
unnötig oft zu schreiben). `HemsBridge.async_setup()` registriert zusätzlich zum bestehenden
`async_track_state_change_event`-Listener einen `async_track_time_interval`-Listener, der
`_async_sync()` erneut aufruft. `_async_sync()` selbst bleibt unverändert: die bestehende
`_enabled`-Prüfung (D-011) und `mode_changed`-Logik (D-009) gelten für Keep-Alive-Ticks genauso
wie für Helfer-Events — ein Keep-Alive während der Pause schreibt nichts, ein Keep-Alive bei
unveränderter Betriebsart löst keinen Zero-Zwischenschritt aus. `async_unload()` entfernt beide
Listener.

D-008 bleibt in der Kernentscheidung (Passive-Mode statt Manual-Mode) unverändert gültig — nur die
Refresh-Annahme ist überholt, Status dort entsprechend auf „Ersetzt durch D-012" gesetzt (Zeile
bleibt stehen, siehe Ablauf-Regel in `design-entscheidungen.md`).

## Folgen

- **Positiv:** HEMS-Anforderungen, die minutenlang konstant bleiben (z. B. stabiler
  PV-Überschuss), werden nicht mehr durch den Marstek-eigenen Watchdog stillschweigend beendet.
  Kein manuelles Eingreifen (Schalter aus/an) mehr nötig, um die Anbindung wieder zum Laufen zu
  bringen. Beantwortet nebenbei die bisher offene Frage in `bekannte-luecken.md`, ob das Gerät
  nach `cd_time` tatsächlich zurückfällt — ja, live bestätigt.
- **Negativ:** Ein zusätzlicher Timer je Speicher mit HEMS-Präfix, zusätzliche Schreiblast auf dem
  gemeinsamen `_call_lock` (in der Praxis vernachlässigbar gegenüber der ohnehin
  sekundenschnellen Event-Rate bei aktiver HEMS-Anforderung).
- **Aufwand:** `HEMS_KEEPALIVE_INTERVAL` in `const.py`, `_unsub_keepalive`/
  `_async_handle_keepalive()` in `hems_bridge.py`, drei neue Tests in `tests/test_hems_bridge.py`.

## Rücknahmebedingung

Zeigt sich in der Praxis, dass 60 s zu selten ist (z. B. weil ein einzelner verzögerter Tick unter
Last die 300-s-Marge doch reißt) oder unnötig oft schreibt (z. B. spürbare Zusatzlast auf dem
Marstek-Gerät bei vielen parallelen Speichern), wäre das Intervall anzupassen oder — bei
wiederkehrenden Problemen mit dem `_call_lock` — Option C erneut zu prüfen.
