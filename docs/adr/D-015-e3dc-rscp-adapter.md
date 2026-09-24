# D-015: E3DC-Hauskraftwerk als zweiter Adapter über RSCP (pye3dc), Keep-Alive-Takt pro Adapter

- **Datum:** 23.09.2026
- **Status:** Aktiv
- **Betrifft:** `adapters/e3dc_rscp.py` (neu), `adapters/base.py`, `adapters/marstek_udp.py`,
  `hems_bridge.py`, `number.py`, `const.py`, `config_flow.py`, `__init__.py`, `manifest.json`,
  `pyproject.toml`, `strings.json`, `translations/de.json`

## Kontext

Neben dem Marstek-Speicher soll ein E3DC-Hauskraftwerk über dieselben Entities (SoC,
Ist-/Soll-Lade-/Entladeleistung, HEMS-Soll-Sensoren, Schalter „HEMS-Steuerung") bereitstehen und
von SkytechHEMS gesteuert werden. In Home Assistant läuft die Steuerung bisher über ein pyscript
(`pyscript.e3dc_start_manual_power`), das über die Bibliothek pye3dc den RSCP-Befehl
`EMS_REQ_SET_POWER` mit Betriebsart und Leistung sendet, gehalten von der Automation
„E3DC Manuelle Leistung", die den Befehl alle 6 s wiederholt.

Zwei Eigenheiten unterscheiden E3DC von Marstek:

1. **Kurze Rückfallzeit:** E3DC übernimmt nach rund 10 s ohne neuen Sollwert selbst wieder die
   Regelung. Der bisher feste Keep-Alive-Takt der HEMS-Anbindung (60 s, D-012) ist dafür viel zu
   lang — auch ein Sollwert von 0 W muss laufend erneuert werden.
2. **Zugangsdaten:** RSCP verlangt Benutzername und Passwort des E3DC-Portalkontos sowie den am
   Gerät hinterlegten RSCP-Schlüssel. Marstek läuft ohne Anmeldung.

## Betrachtete Optionen

### Option A — Eigener Adapter über pye3dc, Keep-Alive-Takt als Adapter-Eigenschaft (gewählt)

- Dafür: Invariante 1 bleibt gewahrt — Coordinator und Platforms kennen weiterhin nur das
  Protocol. pye3dc ist die Bibliothek, mit der die Steuerung heute nachweislich funktioniert.
  Der Takt hängt am Gerät, nicht an der HEMS-Anbindung — dort gehört er hin.
- Dagegen: Erste Laufzeit-Abhängigkeit der Integration; pye3dc ist synchron und muss im Executor
  laufen.

### Option B — Istwerte über die vorhandenen Modbus-Entities lesen, nur Schreiben über RSCP

- Dafür: Keine zweite Leseverbindung zum Gerät.
- Dagegen: Integration hinge von fremden Entities ab, die jeder Nutzer anders nennt; zwei Wege
  zum selben Gerät. Vom User verworfen.

### Option C — Keep-Alive global auf 5 s senken

- Dafür: Keine Protocol-Änderung.
- Dagegen: Marstek bekäme zwölfmal so viele Schreibbefehle ohne Nutzen — genau die Last, die am
  Marstek-Chip schon zu Aussetzern geführt hat (D-013, D-014).

## Entscheidung

Option A. Festgelegt mit dem User am 23.09.2026:

- **Schreiben:** RSCP `EMS_REQ_SET_POWER`. Soll-Ladeleistung > 0 → Betriebsart 4 „Netzladen"
  (lädt den Sollwert notfalls aus dem Netz, wie der Marstek-Passive-Mode und wie die bisherige
  Automation). Soll-Entladeleistung > 0 → Betriebsart 2 „Entladen". Sollwert 0 → Betriebsart 1
  „Leerlauf".
- **Lesen:** ebenfalls über RSCP (`E3DC.poll()`: `stateOfCharge`, `consumption.battery`, positiv =
  laden).
- **Keep-Alive:** `StorageAdapter` bekommt das Attribut `keepalive_interval`; Marstek 60 s
  (unverändert, D-012), E3DC 5 s. Ebenso `max_power_w` für die Obergrenze der Soll-Entities —
  Marstek 10 kW, E3DC aus der Anlagenkennung (`maxBatChargePower`/`maxBatDischargePower`),
  ersatzweise 12 kW.
- **Zugangsdaten:** im Config-Entry, wie von Home Assistant vorgesehen; Passwort und
  RSCP-Schlüssel als maskierte Felder, nie im Log. Falsche Zugangsdaten melden sich im Config-Flow
  als eigener Hinweis (`StorageAdapterAuthError`).
- **unique_id:** `e3dc_<Seriennummer>`, ersatzweise `e3dc_<Host>:<Port>` — bleibt bei neuer IP
  gleich.
- **Schalter „HEMS-Steuerung" aus:** wie bei Marstek wird nichts gesendet; E3DC übernimmt nach
  rund 10 s selbst.
- **Neuaufbau der Verbindung:** übernimmt pye3dc selbst (trennt nach einem Fehler, meldet sich
  beim nächsten Aufruf neu an) — kein eigener Mechanismus wie D-013 nötig.

## Folgen

- **Positiv:** Zweiter Hersteller ohne Änderung an Coordinator, Sensoren oder Schalter; die
  pyscript-Automation „E3DC Manuelle Leistung" wird für HEMS nicht mehr gebraucht.
- **Negativ:** Laufzeit-Abhängigkeit `pye3dc` (fest auf 0.10.0 gepinnt). Bei aktiver
  HEMS-Anbindung gehen alle 5 s ein oder zwei RSCP-Befehle an das Gerät.
  `number.<prefix>_soll_*` von Hand gesetzt hält bei E3DC nur rund 10 s (kein Keep-Alive auf
  diesem Pfad).
- **Aufwand:** Neuer Adapter, Config-Flow-Schritt, Protocol-Attribute, Tests, Doku.

## Rücknahmebedingung

Fällt E3DC trotz 5-s-Takt regelmäßig in die Eigenregelung zurück (Ist-Leistung springt zwischen
Sollwert und Eigenverbrauchsregelung), oder bleiben RSCP-Aufrufe länger als ein Takt hängen, ist
der Ansatz über pye3dc/Executor zu überdenken (z. B. eigene asynchrone RSCP-Anbindung).
