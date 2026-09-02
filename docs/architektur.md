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
| Sprache / Laufzeit | Python 3.13+, Home Assistant Custom Component, `asyncio` | Von aktuellem HA-Core/`pytest-homeassistant-custom-component` vorausgesetzt — Plan nannte 3.11, siehe [bekannte-luecken.md](bekannte-luecken.md) |
| Transport (Marstek) | UDP JSON-RPC, Port 30000 | Offizielle lokale Open-API, geringerer Overhead als Modbus TCP, kein Firmware-Mindeststand nötig — siehe D-007 |
| Persistenz | Keine eigene — HA-State/Config-Entries | Nicht-Ziel, siehe oben |
| Schnittstelle | HA-Entities (`sensor`, `number`) je Speicher-Instanz | Einzige öffentliche Schnittstelle dieses Projekts, siehe [api-referenz.md](api-referenz.md) |
| Tests | `pytest` + `pytest-homeassistant-custom-component` | Deterministisch, ohne Netzwerkzugriff, gegen den echten HA-Testkern — Details: [test-strategie.md](test-strategie.md) |
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
| `sensor.py` | `StorageState`-Felder als HA-Entities abbilden | Eigene Poll- oder Verbindungslogik — das ist Aufgabe des Coordinators/Adapters |
| `number.py` | Soll-Werte entgegennehmen, Schreibaufrufe an den Adapter durchreichen, Fehler als HA-Fehler melden | Eigene Poll- oder Verbindungslogik |

Regel: Keine Komponente übernimmt Aufgaben einer anderen. Verschiebt sich eine Verantwortung,
ist das eine Design-Entscheidung → [design-entscheidungen.md](design-entscheidungen.md).

## Datenfluss

`config_flow.py` legt pro physischem Speicher einen `ConfigEntry` an (Hersteller, Protokoll,
Verbindungsdaten), nach einem erfolgreichen Verbindungstest (`adapter.connect()` + `read()`).
`__init__.py` baut daraus den passenden Adapter, erzeugt einen `BatteryBridgeCoordinator`
(`coordinator.py`) und ruft `async_config_entry_first_refresh()` — schlägt das fehl, kommt
`ConfigEntryNotReady`, HA versucht den Start automatisch erneut. Danach fragt der Coordinator im
festen Poll-Intervall `StorageAdapter.read()` ab und erhält ein `StorageState`
(Schema: [datenmodell.md](datenmodell.md)). `sensor.py` liest den zuletzt bekannten Zustand vom
Coordinator und bildet ihn als `sensor.*`-Entities ab. Schlägt eine Abfrage nach Retries fehl,
wirft der Adapter `StorageAdapterError`, der Coordinator übersetzt das in `UpdateFailed` und die
Entities werden `unavailable` — kein Crash, kein Reload nötig.

Der Schreibpfad läuft ohne Umweg über den Coordinator: `number.py` ruft bei jeder Wertänderung
direkt `adapter.write_charge_power()`/`write_discharge_power()` auf, meldet einen Fehlschlag als
`HomeAssistantError` (nie still) und stößt bei Erfolg `coordinator.async_request_refresh()` an,
damit die Ist-Werte zeitnah nachziehen. Kein aktiver Refresh-Loop hält den Sollwert am Leben —
das übernimmt der `cd_time`-Watchdog im Adapter selbst (D-008). **Unverifiziert an echter
Hardware**, siehe [bekannte-luecken.md](bekannte-luecken.md).

Details zur öffentlichen Schnittstelle (Entities, Adapter-Vertrag): [api-referenz.md](api-referenz.md).

## Verzeichnisstruktur

```text
custom_components/battery_bridge/
├── __init__.py                # Setup/Unload ConfigEntry, Adapter+Coordinator anlegen, PLATFORMS
├── manifest.json               # domain, name, codeowners, requirements, iot_class: local_polling
├── config_flow.py               # Schritt 1: Hersteller wählen · Schritt 2: Verbindungsdaten je Hersteller
├── const.py                     # DOMAIN, Config-Keys, Poll-Intervall, Hersteller-/Protokoll-IDs
├── coordinator.py                # BatteryBridgeCoordinator(DataUpdateCoordinator[StorageState])
├── models.py                      # StorageState (Dataclass)
├── adapters/
│   ├── __init__.py
│   ├── base.py                     # StorageAdapter-Protocol, StorageAdapterError
│   └── marstek_udp.py               # Marstek Local API, UDP JSON-RPC Port 30000 — Lesen+Schreiben
├── sensor.py                        # SoC-%, Ist-Ladeleistung-W, Ist-Entladeleistung-W
├── number.py                         # Soll-Ladeleistung-W, Soll-Entladeleistung-W
└── strings.json / translations/de.json   # Config-Flow- und Entity-Texte (identisch, siehe unten)

tests/
├── adapters/test_marstek_udp.py   # gegen gemockten Transport, kein echter Socket
├── test_coordinator.py             # gegen den echten HA-Testkern (hass-Fixture)
├── test_config_flow.py              # ebenso
├── test_number.py                    # ebenso
└── conftest.py                        # gemeinsame Test-Helfer (MockConfigEntry, Entity-Lookup)

hacs.json, pyproject.toml            # HACS-Metadaten, uv-Projekt + Dev-Dependencies
```

`strings.json` und `translations/de.json` sind bewusst identisch (nicht Englisch→Übersetzung):
Regel 3 in [`AGENTS.md`](../AGENTS.md) verlangt deutsche UI-Texte ohne Ausnahme, `strings.json`
ist außerdem der Fallback, wenn eine HA-Instanz nicht auf Deutsch steht.

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
ruff check .
pytest
```

`hassfest` und die HACS-Validierung sind **keine lokal ausführbaren Befehle** — beide laufen als
GitHub Actions (`.github/workflows/hassfest.yml`, `hacs.yml`), so wie HA-Integrationen sie
standardmäßig prüfen (kein pip-Paket dafür). Konfiguration: [konfiguration.md](konfiguration.md).
