# API-Referenz

> Dieses Projekt hat keine eigene REST-API. Seine öffentlichen Schnittstellen sind (1) die
> HA-Entities, die andere Komponenten (allen voran SkytechHEMS) konsumieren, und (2) das
> `StorageAdapter`-Protocol als Erweiterungspunkt für neue Hersteller/Protokolle.

## Entities pro Speicher-Instanz

Präfix (`<prefix>`) wird im Config-Flow je Entry vergeben, alle Entities eines Entry teilen sich
ein `device_info` (Hersteller, Modell, `unique_id` des Entry).

| Entity | Plattform | Einheit | Richtung | Stand |
|---|---|---|---|---|
| `sensor.<prefix>_soc` | sensor | % | lesen | umgesetzt (M1) |
| `sensor.<prefix>_ist_ladeleistung` | sensor | W | lesen | umgesetzt (M1) |
| `sensor.<prefix>_ist_entladeleistung` | sensor | W | lesen | umgesetzt (M1) |
| `number.<prefix>_soll_ladeleistung` | number | W | schreiben | geplant, siehe [roadmap.md](roadmap.md) M2 |
| `number.<prefix>_soll_entladeleistung` | number | W | schreiben | geplant, siehe [roadmap.md](roadmap.md) M2 |

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
stillen Fehlschlag. In `MarstekUdpAdapter` werfen beide aktuell `NotImplementedError` — der
Schreibpfad ist erst mit M2 dran, siehe [bekannte-luecken.md](bekannte-luecken.md).

## Fremde Schnittstellen

Von diesem Projekt **genutzte** externe Endpunkte:

| Dienst | Methode (JSON-RPC) | Wofür | Stand |
|---|---|---|---|
| Marstek Local API, UDP Ziel-IP:30000 (konfigurierbar) | `ES.GetStatus` | SoC (`bat_soc`) + Lade-/Entladeleistung (`bat_power`) lesen | umgesetzt (M1) |
| Marstek Local API | `Bat.GetStatus` | Detaillierterer Batteriestatus (Temperatur, Kapazität) — von dieser Integration bisher nicht genutzt | nicht genutzt |
| Marstek Local API | `ES.SetMode` | Lade-/Entladeleistung schreiben (Passive- oder Manual-Mode, ungeklärt) | geplant (M2) |
| Marstek Local API | `Marstek.GetDevice` | Geräte-Discovery per UDP-Broadcast | nicht umgesetzt, siehe [roadmap.md](roadmap.md) |

Timeout+Retry bei jedem Aufruf: 3× à 1 s, danach `StorageAdapterError` → `UpdateFailed` →
Entities `unavailable`, kein Crash (siehe [architektur.md](architektur.md)).

Feldbedeutungen nicht hier duplizieren, sondern nach [datenmodell.md](datenmodell.md) verlinken.
Quellenlage und offene Fragen zum Marstek-Protokoll: [bekannte-luecken.md](bekannte-luecken.md).
