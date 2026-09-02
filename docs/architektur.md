# Architektur

> Beschreibt den **tatsächlichen** Stand. Geplantes, aber nicht Umgesetztes gehört nach
> [roadmap.md](roadmap.md), Abweichungen nach [bekannte-luecken.md](bekannte-luecken.md).

## Zweck und Abgrenzung

Home-Assistant-Integration, die Batteriespeicher verschiedener Hersteller (Marstek zuerst) einheitlich als normalisierte HA-Entitäten bereitstellt: Ist-SoC und Ist-Lade-/Entladeleistung lesen, Soll-Lade-/Entladeleistung schreiben. Brücke zwischen Herstelleranbindung und generischen Verbrauchern wie SkytechHEMS.

**Nicht** Aufgabe dieses Projekts:

- Kein Ersatz des bestehenden HEMS-Anforderungsvertrags
  (`input_number.ems_<prefix>_anforderung_leistung_w` /
  `input_select.ems_<prefix>_anforderung_betriebsart`) — diese Integration ersetzt nur die
  Geräteautomation dahinter, nicht den Vertrag selbst.
- Keine eigene Persistenz — HA-State und Config-Entries reichen.
- Kein Cloud-Zugriff auf Herstellerserver — ausschließlich lokal (LAN).
- Keine Regel- oder Verteilungslogik — die bleibt vollständig bei SkytechHEMS.
- Kein direktes Schalten von Endgeräten außerhalb der eigenen Speicher-Entities (HEMS-Architekturgrenze).

## Tech-Stack

| Schicht | Technologie | Warum |
|---|---|---|
| Sprache / Laufzeit | Python 3.11, Home Assistant Custom Component, `asyncio` | Setzt sich aus dem HA-Integrations-Framework selbst voraus, keine eigene Wahl |
| Transport (Marstek) | UDP JSON-RPC, Port 30000 | Offizielle lokale Open-API, geringerer Overhead als Modbus TCP, kein Firmware-Mindeststand nötig — siehe D-007 |
| Persistenz | Keine eigene — HA-State/Config-Entries | Nicht-Ziel, siehe oben |
| Schnittstelle | HA-Entities (`sensor`, `number`) je Speicher-Instanz | Einzige öffentliche Schnittstelle dieses Projekts, siehe [api-referenz.md](api-referenz.md) |
| Tests | `pytest`, UDP-Mock/Fixture statt echter Hardware | Deterministisch, ohne Netzwerkzugriff — [test-strategie.md](test-strategie.md) |
| Linting | `ruff check .` | Projektstandard, siehe [`AGENTS.md`](../AGENTS.md) |

## Komponenten

```text
  ┌────────────┐  Hersteller× ┌───────────────┐  liefert    ┌─────────────┐
  │ ConfigFlow │ ─Protokoll──►│ StorageAdapter│─StorageState►│ Coordinator │
  │ (UI-Setup) │  wählen      │ (z. B. marstek_udp)          │ (Polling)   │
  └────────────┘              └───────┬───────┘              └──────┬──────┘
                                       │ write_charge_power()        │ liest
                                       │ write_discharge_power()     ▼
                                       │                      ┌─────────────┐
                                       └─────────────────────►│  Platforms  │
                                                               │ sensor.py   │
                                                               │ number.py   │
                                                               └──────┬──────┘
                                                                      │ Entities
                                                                      ▼
                                                     HA-Core (Dashboards, HEMS, Automationen)
```

| Komponente | Verantwortung | Darf nicht |
|---|---|---|
| `config_flow.py` | Hersteller/Protokoll wählen, Verbindungsdaten abfragen, Verbindungstest vor Anlage des Entry | Speicherzustand lesen/schreiben außerhalb des einmaligen Tests |
| `adapters/*.py` (`StorageAdapter`) | Ein Protokoll/Hersteller sprechen: `connect()`/`read()`/`write_*()`/`close()` | Wissen, wie Coordinator oder Platforms mit den Daten umgehen |
| `coordinator.py` | Adapter im Poll-Intervall abfragen, `StorageState` an Platforms verteilen, Fehler in `UpdateFailed`/`ConfigEntryNotReady` übersetzen | Herstellerspezifisches Protokoll kennen — nur über `StorageAdapter` |
| `sensor.py` / `number.py` | `StorageState`-Felder als HA-Entities abbilden, Schreibaufrufe an den Adapter durchreichen | Eigene Poll- oder Verbindungslogik — das ist Aufgabe des Coordinators/Adapters |

Regel: Keine Komponente übernimmt Aufgaben einer anderen. Verschiebt sich eine Verantwortung,
ist das eine Design-Entscheidung → [design-entscheidungen.md](design-entscheidungen.md).

## Datenfluss

`config_flow.py` legt pro physischem Speicher einen `ConfigEntry` an (Hersteller, Protokoll,
Verbindungsdaten). `__init__.py` erzeugt daraus einen `coordinator.py`, der im festen
Poll-Intervall den zugehörigen `StorageAdapter.read()` aufruft und ein `StorageState` erhält
(Schema: [datenmodell.md](datenmodell.md)). `sensor.py` liest den zuletzt bekannten Zustand vom
Coordinator und bildet ihn als `sensor.*`-Entities ab. Schreibt ein Nutzer oder eine Automation
einen Wert auf `number.*`, ruft `number.py` direkt `adapter.write_charge_power()` bzw.
`write_discharge_power()` auf und meldet Erfolg/Fehler zurück — ohne Umweg über den Coordinator.
Schlägt eine Abfrage nach Retries fehl, setzt der Coordinator die Entities `unavailable`
(Details: [bekannte-luecken.md](bekannte-luecken.md), Abschnitt Reaktionszeit).

Details zur öffentlichen Schnittstelle (Entities, Adapter-Vertrag): [api-referenz.md](api-referenz.md).

## Verzeichnisstruktur

```text
custom_components/battery_bridge/
├── __init__.py          # Setup/Unload ConfigEntry, Coordinator anlegen
├── manifest.json         # domain, name, codeowners, requirements, iot_class: local_polling
├── config_flow.py         # Schritt 1: Hersteller wählen · Schritt 2: Verbindungsdaten je Hersteller
├── const.py               # DOMAIN, Plattform-Konstanten, Default-Poll-Intervall
├── coordinator.py          # DataUpdateCoordinator[StorageState] pro ConfigEntry
├── models.py                # StorageState (Dataclass)
├── adapters/
│   ├── __init__.py
│   ├── base.py               # StorageAdapter-Protocol
│   └── marstek_udp.py         # Marstek Open API, UDP JSON-RPC Port 30000
├── sensor.py                  # SoC-%, Ist-Ladeleistung-W, Ist-Entladeleistung-W
├── number.py                   # Soll-Ladeleistung-W, Soll-Entladeleistung-W
├── strings.json / translations/de.json   # Config-Flow-Texte
```

Vollständige Datei- und Testübersicht inklusive `tests/`: [plan.md](../plan.md) Abschnitt 3, bis
diese Doku nach der ersten Implementierung den tatsächlichen Stand übernimmt.

## Invarianten

Zusagen, auf die sich der gesamte Code verlässt. Wer eine davon bricht, bricht das System:

1. Coordinator und Platforms kennen nur das `StorageAdapter`-Protocol, nie Herstellerdetails — ein
   neuer Adapter ist eine neue Datei unter `adapters/`, keine Änderung an Coordinator/Platforms.
2. `StorageState.soc_percent`/`charge_power_w`/`discharge_power_w` sind `None`, wenn der Wert
   ungültig ist — nie ein geratener oder zuletzt bekannter Ersatzwert.
3. Schreiboperationen (`write_charge_power`/`write_discharge_power`) melden Erfolg oder Fehler an
   den Aufrufer zurück — nie ein stiller Fehlschlag.
4. Diese Integration schaltet ausschließlich die eigenen Speicher-Entities — nie andere
   Endgeräte direkt (HEMS-Architekturgrenze, siehe Abgrenzung oben).

## Start und Betrieb

```bash
uv sync
hassfest && hacs validate
```

Konfiguration: [konfiguration.md](konfiguration.md).
