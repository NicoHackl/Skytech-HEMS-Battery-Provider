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
| `number.<prefix>_soll_ladeleistung` | number | W | schreiben | umgesetzt, unverifiziert an Hardware (M2) |
| `number.<prefix>_soll_entladeleistung` | number | W | schreiben | umgesetzt, unverifiziert an Hardware (M2) |
| `sensor.<prefix>_hems_soll_ladeleistung` | sensor | W | lesen | umgesetzt (D-010), nur mit HEMS-Präfix |
| `sensor.<prefix>_hems_soll_entladeleistung` | sensor | W | lesen | umgesetzt (D-010), nur mit HEMS-Präfix |
| `switch.<prefix>_hems_steuerung_aktiv` | switch | – | schreiben | umgesetzt (D-011), nur mit HEMS-Präfix |

`number.*` liest sich nicht vom Gerät zurück (weder die Marstek Local API noch E3DC-RSCP bieten
dafür einen Read-Pfad) — die Entity zeigt den zuletzt erfolgreich gesendeten Wert (`assumed_state`), nicht
zwingend den tatsächlichen Gerätezustand.

`None`/`available=False` im zugrundeliegenden `StorageState` löst `unavailable` aus — Details:
[datenmodell.md](datenmodell.md).

## HEMS-Anbindung (optional, `hems_bridge.py`)

Im Config-Flow lässt sich pro Entry ein `hems_entity_prefix` hinterlegen (leer = deaktiviert,
Default). Ist er gesetzt, liest diese Integration selbst laufend zwei fremde, von SkytechHEMS
verwaltete Entities:

| Entity | Domain | Bedeutung |
|---|---|---|
| `input_number.ems_<hems_entity_prefix>_anforderung_leistung_w` | lesen | Signierter Sollwert: positiv = laden, negativ = entladen |
| `input_select.ems_<hems_entity_prefix>_anforderung_betriebsart` | lesen | `laden` / `entladen` / `standby` |

und übersetzt jede Änderung in `adapter.write_charge_power()`/`write_discharge_power()` — in
dieser Reihenfolge zuerst die inaktive Richtung auf `0`, danach die aktive Richtung (Details:
[architektur.md](architektur.md), [design-entscheidungen.md](design-entscheidungen.md) D-009).
Fehlen die beiden Entities (falscher Präfix, HEMS-Gerät noch nicht angelegt) oder ist die
Betriebsart weder `laden` noch `entladen`, bleibt die Integration im sicheren Fall (beide
Richtungen `0`) statt zu raten.

Diese beiden Entities sind der einzige Kontrakt, den diese Integration von SkytechHEMS
konsumiert — sie werden nur gelesen, nie geschrieben.

Den zuletzt tatsächlich gesendeten Sollwert liest man **nicht** an `number.<prefix>_soll_*` ab
(die bleiben davon unberührt, siehe [bekannte-luecken.md](bekannte-luecken.md)), sondern an
`sensor.<prefix>_hems_soll_ladeleistung`/`_hems_soll_entladeleistung` — `assumed_state` wie
`number.*`, `unavailable` bis zum ersten erfolgreichen Sync, bleibt bei einem Schreibfehler
bewusst auf dem letzten bekannten Wert stehen (D-010).

Ein zusätzlicher Schalter, `switch.<prefix>_hems_steuerung_aktiv`, pausiert/setzt die
automatischen Schreibvorgänge dieser Anbindung fort (D-011) — Standard nach jedem Neustart ist
EIN. AUS lässt sich `number.<prefix>_soll_ladeleistung`/`_soll_entladeleistung` manuell setzen,
ohne dass der nächste HEMS-Sync es sofort überschreibt; beim Wiedereinschalten synchronisiert die
Anbindung sofort mit dem aktuellen HEMS-Sollwert, statt auf die nächste Änderung zu warten.

## `StorageAdapter`-Protocol (`adapters/base.py`)

Der Vertrag, den jeder Hersteller-Adapter implementiert — Coordinator und Platforms kennen nur
dieses Protocol, nie Herstellerdetails:

```python
class StorageAdapter(Protocol):
    keepalive_interval: timedelta   # HEMS-Keep-Alive-Takt (Marstek 60 s, E3DC 5 s, D-015)
    max_power_w: int                # Obergrenze der number.*_soll_*-Entities

    async def connect(self) -> None: ...
    async def read(self) -> StorageState: ...
    async def write_charge_power(self, watts: float) -> None: ...
    async def write_discharge_power(self, watts: float) -> None: ...
    async def close(self) -> None: ...
```

`write_charge_power`/`write_discharge_power` melden Fehler über eine Exception, nie über einen
stillen Fehlschlag. `MarstekUdpAdapter` setzt beide über `ES.SetMode` im Passive-Mode um — siehe
[bekannte-luecken.md](bekannte-luecken.md) für Quellenlage und den noch offenen Hardware-Test.
`E3dcRscpAdapter` sendet RSCP `EMS_REQ_SET_POWER`: Laden > 0 → Betriebsart 4 (Netzladen),
Entladen > 0 → Betriebsart 2 (Entladen), 0 W → Betriebsart 1 (Leerlauf) — D-015. Abgelehnte
Zugangsdaten meldet er als `StorageAdapterAuthError` (Unterklasse von `StorageAdapterError`).

## Fremde Schnittstellen

Von diesem Projekt **genutzte** externe Endpunkte:

| Dienst | Methode (JSON-RPC) | Wofür | Stand |
|---|---|---|---|
| Marstek Local API, UDP Ziel-IP:30000 (konfigurierbar) | `ES.GetStatus` | SoC (`bat_soc`) + Lade-/Entladeleistung (`bat_power`) lesen | umgesetzt (M1) |
| Marstek Local API | `Bat.GetStatus` | Detaillierterer Batteriestatus (Temperatur, Kapazität) — von dieser Integration bisher nicht genutzt | nicht genutzt |
| Marstek Local API | `ES.SetMode` (Passive-Mode) | Lade-/Entladeleistung schreiben, `power` + `cd_time`-Watchdog | umgesetzt, unverifiziert an Hardware (M2) |
| Marstek Local API | `Marstek.GetDevice` | Geräte-Discovery per UDP-Broadcast | nicht umgesetzt, siehe [roadmap.md](roadmap.md) |
| E3DC RSCP, TCP Ziel-IP:5033 (konfigurierbar), über `pye3dc` | `E3DC.poll()` (`EMS_REQ_BAT_SOC`, `EMS_REQ_POWER_BAT` u. a.) | SoC + Batterieleistung lesen (positiv = laden) | umgesetzt (D-015) |
| E3DC RSCP | `EMS_REQ_SET_POWER` (`EMS_REQ_SET_POWER_MODE`, `EMS_REQ_SET_POWER_VALUE`) | Lade-/Entladeleistung schreiben, hält rund 10 s | umgesetzt, an Hardware zu bestätigen (D-015) |

Timeout+Retry bei jedem Marstek-Aufruf: 3× à 1 s (E3DC: pye3dc-eigene 3 Wiederholungen, 5 s
Socket-Timeout), danach `StorageAdapterError` → `UpdateFailed` →
Entities `unavailable`, kein Crash (siehe [architektur.md](architektur.md)).

Feldbedeutungen nicht hier duplizieren, sondern nach [datenmodell.md](datenmodell.md) verlinken.
Quellenlage und offene Fragen zum Marstek-Protokoll: [bekannte-luecken.md](bekannte-luecken.md).
