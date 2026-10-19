# Datenmodell

Gemeinsamer Schnittstellenstand: [HEMS-Vertrag](../contract/contract_hems_battery_provider/contract_hems_battery_provider.md).

> Enthält nur, was **wirklich** persistiert oder zwischen Komponenten ausgetauscht wird.
> Trifft auf dieses Projekt nichts davon zu: Datei löschen und aus
> [README.md](README.md) austragen.

## Identitäten

| Bezeichner | Bedeutung | Vergeben von | Unveränderlich |
|---|---|---|---|
| `ConfigEntry.unique_id` | Identifiziert einen physischen Speicher — Marstek: `<Host>:<Port>`; E3DC: `e3dc_<Seriennummer>`, ersatzweise `e3dc_<Host>:<Port>` (D-015) | `config_flow.py` beim Anlegen | ja |
| `<prefix>` | Entity-Präfix eines Speichers (z. B. `marstek_venus1`) | User im Config-Flow, aus Anzeigename abgeleitet | nein — Anzeigename kann geändert werden, `unique_id` bleibt gleich |

Grundsatz: `<prefix>` bzw. Entity-IDs sind **nie** der Primärschlüssel, mit dem ein Speicher
wiedererkannt wird — das ist ausschließlich `unique_id`. Ändert der User den Anzeigenamen, bleibt
derselbe Entry bestehen, es entsteht kein doppelter.

## Schema

`StorageState` (`models.py`), das Ergebnis eines Adapter-`read()`:

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `soc_percent` | `float \| None` | ja | Ladezustand in %, `None` bei ungültigem Wert |
| `charge_power_w` | `float \| None` | ja | Ist-Ladeleistung ≥ 0 |
| `discharge_power_w` | `float \| None` | ja | Ist-Entladeleistung ≥ 0 |
| `available` | `bool` | ja | Letzte Abfrage erfolgreich |
| `last_update` | `datetime` | ja | Zeitstempel der letzten gültigen Antwort |
| `charge_allowed` | `bool \| None` | nein | Ladefreigabe des Geräts (D-017); `None` = Gerät liefert keine Angabe |
| `discharge_allowed` | `bool \| None` | nein | Entladefreigabe des Geräts (D-017); `None` = Gerät liefert keine Angabe |
| `lock_reasons` | `tuple[str, ...]` | nein | Stabile Sperrgründe: `geraet_laden_gesperrt`, `geraet_entladen_gesperrt`, `ladesperrzeit`, `entladesperrzeit`, `notstromreserve`, `keine_reaktion_laden`, `keine_reaktion_entladen` |
| `temperature_c` | `float \| None` | nein | Batterietemperatur in °C (Marstek `bat_temp`) |
| `rated_capacity_wh` | `float \| None` | nein | Nennkapazität in Wh (Marstek `rated_capacity`) |
| `raw_status` | `int \| None` | nein | Rohes Statusbitfeld des Geräts (E3DC `EMS_STATUS`), nur Diagnose |
| `lock_release_soc_percent` | `float \| None` | nein | Ladezustand, ab dem eine vom Soll/Ist-Vergleich erkannte Sperre fällt (D-018) |

Herkunft der Gerätestatus-Felder je Adapter (höchstens alle `STATUS_POLL_INTERVAL` = 15 s gelesen):

| Feld | Marstek (`Bat.GetStatus`) | E3DC (RSCP) |
|---|---|---|
| `charge_allowed` | `charg_flag` und kein Soll/Ist-Befund `keine_reaktion_laden` (D-018) | nicht Bit 0 (Laden gesperrt) und nicht Bit 5 (Ladesperrzeit) von `EMS_STATUS` |
| `discharge_allowed` | `dischrg_flag` und kein Soll/Ist-Befund `keine_reaktion_entladen` (D-018) | nicht Bit 1 (Entladen gesperrt), nicht Bit 6 (Entladesperrzeit), nicht `emergencyReserveReached` aus `get_system_status()` |

Bedeutung im unteren SoC-Band (Marstek) und Bitbelegung (E3DC) sind an Hardware zu bestätigen,
siehe [bekannte-luecken.md](bekannte-luecken.md#gerätefreigaben--an-hardware-zu-bestätigen-d-017).

`HemsCommandState` (`hems_bridge.py`), Snapshot des zuletzt erfolgreich an den Adapter gesendeten
HEMS-Sollwerts — **andere Herkunft als `StorageState`**: nicht vom Adapter-Poll gelesen, sondern
von der HEMS-Anbindung selbst gehalten, deshalb eine eigene, kleinere Dataclass statt eines
weiteren `StorageState`-Felds:

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `charge_power_w` | `float` | ja | Zuletzt gesendete Ladeleistung ≥ 0 |
| `discharge_power_w` | `float` | ja | Zuletzt gesendete Entladeleistung ≥ 0 |

`HemsBridge.last_command` ist `None`, solange noch kein Sync erfolgreich war (dieselbe
Leerzustand-Konvention wie bei `StorageState`-Feldern: nie eine geratene 0 vortäuschen). Speist
die Sensoren `sensor.<prefix>_hems_soll_ladeleistung`/`_hems_soll_entladeleistung` — nur
vorhanden, wenn der Entry ein HEMS-Präfix hat.

`HemsRequestState` (`hems_bridge.py`, Property `HemsBridge.request`): Stand der beiden
HEMS-Helfer, wie die Anbindung sie liest — `mode` (Text oder `None`, wenn der Helfer fehlt) und
`power_w` (signiert wie im Helfer, `None` bei fehlendem oder nicht numerischem Wert). Nur Spiegel
für den Schnittstellen-Sensor, keine Regelgröße.

## Datenverträge

- Gerätestatus-Felder `None` heißen „das Gerät sagt dazu nichts", nie „gesperrt". Scheitert nur
  die Statusabfrage, bleibt der Messwert-Poll gültig.

- `None` bedeutet „nicht verfügbar" (ungültige/fehlgeschlagene Abfrage), `0` bedeutet eine
  gemessene Nullleistung. Die beiden werden nie vermischt — ein Adapter, der einen Timeout hat,
  liefert `None`, nie `0`.
- `available=False` macht die Messsensoren nicht verfügbar. Die HEMS-Sollsensoren haben eine
  eigene Verfügbarkeitsprüfung über `last_command` und `write_ok`; sie spiegeln keinen Poll.
  SkytechHEMS behandelt ungültige Speicher-Messwerte über seinen sicheren Ausgabezustand.
- **Erzeuger (Adapter) sind strikt:** nur Werte schreiben, die die Herstellerantwort tatsächlich
  hergibt — kein Interpolieren oder Erraten fehlender Felder.
- **Verbraucher (Coordinator, Platforms) sind tolerant** gegenüber `None`-Feldern, nie gegenüber
  einem `StorageAdapter`, der das Protocol nicht vollständig implementiert.
- Schreiboperationen (`write_charge_power`/`write_discharge_power`) sind pro Aufruf atomar: sie
  melden Erfolg oder Fehler zurück, es gibt keinen Zwischenzustand.

## Migrationen

Entfällt — keine eigene Persistenz, `StorageState` wird pro Poll neu erzeugt, nichts wird
zwischen Neustarts migriert. `ConfigEntry`-Daten folgen dem Standard-Migrationsmechanismus von
Home Assistant (`async_migrate_entry`), falls sich das Schema eines Entry je ändert.

Ändert sich `StorageState`, müssen im **selben** Arbeitspaket geändert werden:

1. `models.py`
2. alle Adapter (`adapters/*.py`) und Platforms (`sensor.py`, `number.py`)
3. Testfixtures
4. diese Datei
