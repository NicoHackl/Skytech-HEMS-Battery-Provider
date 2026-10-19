"""Datenmodell, das jeder Adapter liefert — siehe docs/datenmodell.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class StorageState:
    """Normalisierter Zustand eines Batteriespeichers, herstellerunabhängig.

    `None` bedeutet „nicht verfügbar" (ungültige oder fehlgeschlagene Abfrage),
    `0` bedeutet eine gemessene Nullleistung — die beiden werden nie vermischt.

    Die Gerätestatus-Felder ab `charge_allowed` (D-017) sind optional: ein Adapter, der sie nicht
    liest, oder eine fehlgeschlagene Statusabfrage lässt sie auf `None` — „das Gerät sagt dazu
    nichts", nicht „gesperrt". `lock_reasons` nennt, *warum* das Gerät eine Richtung sperrt,
    als stabile Schlüssel (siehe docs/datenmodell.md), nie als Anzeigetext.
    """

    soc_percent: float | None
    charge_power_w: float | None
    discharge_power_w: float | None
    available: bool
    last_update: datetime
    charge_allowed: bool | None = None
    discharge_allowed: bool | None = None
    lock_reasons: tuple[str, ...] = field(default_factory=tuple)
    temperature_c: float | None = None
    rated_capacity_wh: float | None = None
    raw_status: int | None = None
    # Ladezustand, ab dem eine vom Adapter erkannte Nichtreaktion wieder freigegeben wird (D-018).
    lock_release_soc_percent: float | None = None
