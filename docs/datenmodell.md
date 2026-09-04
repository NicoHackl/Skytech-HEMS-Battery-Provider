# Datenmodell

> Enthält nur, was **wirklich** persistiert oder zwischen Komponenten ausgetauscht wird.
> Trifft auf dieses Projekt nichts davon zu: Datei löschen und aus
> [README.md](README.md) austragen.

## Identitäten

| Bezeichner | Bedeutung | Vergeben von | Unveränderlich |
|---|---|---|---|
| `ConfigEntry.unique_id` | Identifiziert einen physischen Speicher, aus Host+Port (oder Geräte-/MAC-ID, falls die Herstellerantwort eine liefert) | `config_flow.py` beim Anlegen | ja |
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

## Datenverträge

- `None` bedeutet „nicht verfügbar" (ungültige/fehlgeschlagene Abfrage), `0` bedeutet eine
  gemessene Nullleistung. Die beiden werden nie vermischt — ein Adapter, der einen Timeout hat,
  liefert `None`, nie `0`.
- `available=False` löst in HA `unavailable` auf allen Entities des Entry aus — Verbraucher wie
  SkytechHEMS behandeln das über ihren eigenen Fallback-auf-sicheren-Zustand, diese Integration
  baut dafür nichts Eigenes.
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
