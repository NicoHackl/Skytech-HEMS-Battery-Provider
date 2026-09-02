# API-Referenz

> Dieses Projekt hat keine eigene REST-API. Seine öffentlichen Schnittstellen sind (1) die
> HA-Entities, die andere Komponenten (allen voran SkytechHEMS) konsumieren, und (2) das
> `StorageAdapter`-Protocol als Erweiterungspunkt für neue Hersteller/Protokolle.

## Entities pro Speicher-Instanz

Präfix (`<prefix>`) wird im Config-Flow je Entry vergeben, alle Entities eines Entry teilen sich
ein `device_info` (Hersteller, Modell, `unique_id` des Entry).

| Entity | Plattform | Einheit | Richtung |
|---|---|---|---|
| `sensor.<prefix>_soc` | sensor | % | lesen |
| `sensor.<prefix>_ist_ladeleistung` | sensor | W | lesen |
| `sensor.<prefix>_ist_entladeleistung` | sensor | W | lesen |
| `number.<prefix>_soll_ladeleistung` | number | W | schreiben |
| `number.<prefix>_soll_entladeleistung` | number | W | schreiben |

`None`/`available=False` im zugrundeliegenden `StorageState` löst `unavailable` aus — Details:
[datenmodell.md](datenmodell.md).

## `StorageAdapter`-Protocol (`adapters/base.py`)

Der Vertrag, den jeder Hersteller-Adapter implementiert — Coordinator und Platforms kennen nur
dieses Protocol, nie Herstellerdetails:

```python
class StorageAdapter(Protocol):
    async def connect(self) -> None: ...
    async def read(self) -> StorageState: ...
    async def write_charge_power(self, watts: float) -> None: ...
    async def write_discharge_power(self, watts: float) -> None: ...
    async def close(self) -> None: ...
```

`write_charge_power`/`write_discharge_power` melden Fehler über eine Exception, nie über einen
stillen Fehlschlag — der Aufrufer (`number.py`) reicht das als HA-Service-Fehler weiter.

## Fremde Schnittstellen

Von diesem Projekt **genutzte** externe Endpunkte:

| Dienst | Endpunkt | Wofür | Verhalten bei Ausfall |
|---|---|---|---|
| Marstek Local API | UDP, Ziel-IP:30000 (konfigurierbar), JSON-RPC | SoC/Leistung lesen, Lade-/Entladeleistung schreiben | Timeout+Retry (3× à 1 s), danach `UpdateFailed` → Entities `unavailable`, kein Crash |

Feldbedeutungen nicht hier duplizieren, sondern nach [datenmodell.md](datenmodell.md) verlinken.
Offene Fragen zum genauen Marstek-Protokoll: [bekannte-luecken.md](bekannte-luecken.md).
