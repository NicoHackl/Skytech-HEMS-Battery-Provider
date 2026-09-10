# D-013: Der Marstek-Adapter baut seinen UDP-Transport selbst neu auf

- **Datum:** 10.09.2026
- **Status:** Aktiv
- **Betrifft:** `adapters/marstek_udp.py`, `coordinator.py`, `const.py`, `hems_bridge.py`,
  `sensor.py`, `tests/adapters/test_marstek_udp.py`, `tests/test_coordinator.py`,
  `tests/test_hems_bridge.py`, `tests/test_sensor.py`

## Kontext

Der Adapter erzeugt seinen UDP-Transport in `connect()` über
`loop.create_datagram_endpoint(..., remote_addr=(host, port))`. Aufgerufen wird `connect()` genau
einmal: `coordinator._async_setup()` läuft in Home Assistant ausschließlich aus
`async_config_entry_first_refresh()` heraus (nachgeschlagen in
`homeassistant/helpers/update_coordinator.py`). Danach lebt derselbe Socket für die gesamte
Lebensdauer des Config-Entry.

Stirbt dieser Socket, meldet sich das nirgends. `asyncio` reicht einen Transportverlust über
`connection_lost()` an das Protocol — das gab es hier nicht. Danach ist jedes weitere `sendto()`
ein stiller No-Op: keine Exception, kein Rückgabewert, nichts im Log. Aus Sicht des Adapters
„antwortet das Gerät nicht mehr", obwohl nie ein Paket das Haus verlassen hat. `_call()` prüfte
lediglich auf `self._transport is None` — und `None` wird das Feld nur beim Entladen des Entry.

### Der Vorfall vom 09./10.09.2026

Vier Ausfälle, rekonstruiert über den HA-Verlauf (`sensor.<prefix>_ladezustand`,
`switch.<prefix>_hems_steuerung`) und das Systemlog:

| Beginn | Ende | Dauer | Ausgang |
|---|---|---|---|
| 09.09.2026 03:54:46 | 03:56:31 | 105 s | selbst erholt |
| 09.09.2026 11:11:06 | 11:22:45 | 11,6 min | selbst erholt |
| 10.09.2026 03:21:52 | 03:21:55 | 3 s | selbst erholt |
| 10.09.2026 04:09:31 | 05:45:43 | 96 min | erst durch Neuladen der Integration |

Im gesamten Zeitraum 114 Fehlermeldungen im 60-s-Takt des Keep-Alive (D-012):
`Marstek <host>:30000 antwortet nach 3 Versuchen nicht auf ES.SetMode.`

Entscheidend ist das Ende des vierten Ausfalls: `sensor.<prefix>_hems_soll_entladeleistung` ging
um 05:45:43.358 auf `unavailable` (Entry wird entladen) und um 05:45:43.703 zurück auf `0.0`
(Entry ist wieder eingerichtet). Der Wert `0.0` steht dort nur, wenn `HemsBridge.last_command`
gesetzt ist — der erste Schreibvorgang auf dem frisch erzeugten Socket kam also binnen 345 ms
durch. Das Gerät war die ganze Zeit erreichbar. Kaputt war ausschließlich der Socket.

Als zweite Ursache ausgeschlossen: ein konkurrierender Client auf demselben Gerät. Die parallel
installierte Modbus-Integration für denselben Speicher ist in HA deaktiviert und nicht geladen.

Nicht ausgeschlossen, aber bewusst nicht Teil dieser Entscheidung: Am 08.09.2026 um 09:22 wurde
`DEFAULT_UPDATE_INTERVAL` von 5 s auf 1 s gesenkt (Commit `2e79878`), ausgeliefert als
`origin/main` `8062b7f` — der Stand, der während der Ausfälle lief. Der erste Ausfall folgte am
nächsten Tag. Ein Poll je Sekunde ist für dieses Gerät viel, zumal ein erfolgloser Poll drei
Sekunden blockiert und derselbe `_call_lock` auch die HEMS-Schreibvorgänge trägt. Der Takt bleibt
auf ausdrücklichen Wunsch des Users unverändert bei 1 s; diese Entscheidung ändert daran nichts,
sie macht den Ausfall nur überlebbar.

### Zweitbefund: der Ausfall war unsichtbar

Während der 96 Minuten zeigte `sensor.<prefix>_hems_soll_entladeleistung` unverändert `0.0`.
Die beiden HEMS-Soll-Sensoren hängen ausschließlich an `last_command`, also am letzten
*erfolgreichen* Schreibvorgang — sie fallen nicht auf, wenn seither jeder Versuch scheitert. Das
ist dasselbe Muster, das `bekannte-luecken.md` schon für den `cd_time`-Fall beschrieben hat:
„Anforderung da, Speicher ignoriert sie" statt „die Anforderung erreicht das Gerät nicht mehr".

## Betrachtete Optionen

### Option A — Der Adapter hält seinen Transport selbst instand (gewählt)

- Dafür: Behebt die Ursache genau dort, wo sie liegt. Der Adapter ist die einzige Stelle, die
  überhaupt weiß, was ein lebender Transport ist. Ein Neuaufbau vergibt einen neuen Quellport und
  entspricht damit exakt dem, was das manuelle Neuladen bewirkt hat — nur ohne Nebenwirkungen.
- Dagegen: Zwei zusätzliche Zustandsfelder im Adapter (`_connected`, `_failed_calls`) und eine
  Fallunterscheidung mehr in `_call_locked()`.

### Option B — Bei wiederholtem Fehler den Config-Entry neu laden

- Dafür: Wenig Code (`hass.config_entries.async_reload`), nutzt exakt den Weg, der von Hand
  funktioniert hat.
- Dagegen: Wirft für ein reines Socket-Problem den gesamten Entry weg — Entities werden neu
  registriert, laufende Zustände gehen verloren, darunter eine bewusst gesetzte Pause der
  HEMS-Steuerung (D-011, überlebt ein Neuladen absichtlich nicht). Ein Reload-Loop bei einem
  dauerhaft nicht erreichbaren Gerät ist zudem deutlich unruhiger als ein neuer Socket.

### Option C — Verbindungslosen Socket verwenden (`local_addr` statt `remote_addr`)

- Dafür: Ein nicht verbundener UDP-Socket bekommt keine ICMP-Fehler zugestellt und kann dadurch
  in weniger Zustände geraten.
- Dagegen: Ändert das Protokollverhalten (Zieladresse bei jedem `sendto()`, Absenderprüfung bei
  jedem Empfang) für eine Ursache, die nicht bewiesen ist — der genaue Weg, auf dem der Transport
  gestorben ist, ließ sich nachträglich nicht mehr feststellen. Behebt außerdem nicht den
  allgemeinen Fall, dass ein Transport aus irgendeinem Grund wegfällt. Wäre nachrüstbar, falls
  Option A das Problem nicht vollständig abstellt.

## Entscheidung

Option A, in drei Teilen:

1. **Adapter (`adapters/marstek_udp.py`).** `_MarstekUdpProtocol` implementiert
   `connection_lost()` und merkt sich den Verlust; `error_received()` hält zusätzlich den letzten
   Fehler fest. `_call_locked()` ruft vorab `_async_ensure_connection()`, das einen toten
   Transport (`None`, `lost`, `is_closing()`) verwirft und neu aufbaut. Nach
   `_RECONNECT_AFTER_FAILED_CALLS` (2) erfolglosen Aufrufen hintereinander wird der Transport
   zusätzlich aktiv weggeworfen, damit der nächste Aufruf einen frischen erzeugt. Jede empfangene
   Antwort — auch eine Fehlerantwort — setzt den Zähler zurück, denn sie beweist, dass der Socket
   lebt. `connect()` wird dabei nicht mehr von außen benötigt; ein nie verbundener Adapter meldet
   weiterhin einen sprechenden Fehler, dafür gibt es das getrennte Feld `_connected`. Zusätzlich
   wird die Antwort-Queue vor jedem Aufruf geleert: eine verspätete Antwort auf einen längst
   abgelaufenen Request hat im nächsten Aufruf nichts zu suchen.
2. **Coordinator (`coordinator.py`, `const.py`).** Antwortet das Gerät nicht, wechselt der
   Poll-Takt von `DEFAULT_UPDATE_INTERVAL` (5 s) auf `FAILED_UPDATE_INTERVAL` (30 s) und beim
   nächsten Erfolg zurück. Ein Gerät, dessen Netzwerkteil ohnehin gerade überfordert ist, wird so
   nicht weiter im Normaltakt mit je drei Versuchen beschickt. 30 s bleiben weit unter dem
   300-s-Watchdog des Passive-Mode.
3. **Sichtbarkeit (`hems_bridge.py`, `sensor.py`).** `HemsBridge` führt `write_ok`. Solange der
   letzte Schreibversuch gescheitert ist, sind die beiden HEMS-Soll-Sensoren `unavailable` statt
   einen unbestätigten Wert zu zeigen. Gemeldet wird nur noch der Beginn einer Ausfallphase als
   Fehler und ihr Ende als Warnung — statt 114-mal derselben Zeile. Denselben Melde-Rhythmus
   verwendet der Adapter für seine Neuaufbau-Meldungen.

## Folgen

- **Positiv:** Ein gestorbener Socket kostet noch etwa zehn Sekunden statt 96 Minuten, ohne dass
  jemand eingreift. Bleibt das Gerät weg, sieht man das in den Entities statt nur im Log.
- **Negativ:** Der Adapter trägt mehr Zustand. Ein häufig kurz nicht erreichbares Gerät bekommt
  öfter einen neuen Quellport — für die Marstek Local API unkritisch, für einen künftigen Adapter
  mit sitzungsgebundenem Protokoll wäre das zu prüfen (D-006).
- **Aufwand:** Rund 100 Zeilen im Adapter, je ein kleiner Eingriff in Coordinator, HEMS-Anbindung
  und Sensoren, neun neue Tests.

## Rücknahmebedingung

Treten die Ausfälle weiterhin auf, obwohl der Adapter neu verbindet, liegt die Ursache nicht am
Socket allein. Erster Kandidat ist dann der Poll-Takt von 1 s (siehe Kontext), danach Option C
(verbindungsloser Socket); die Beobachtung in `bekannte-luecken.md` ist entsprechend zu
korrigieren. Häuft sich umgekehrt der
Neuaufbau bei einem Gerät, das nur kurz zögert, ist `_RECONNECT_AFTER_FAILED_CALLS` zu erhöhen.
