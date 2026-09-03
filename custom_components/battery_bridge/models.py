"""Datenmodell, das jeder Adapter liefert — siehe docs/datenmodell.md."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, kw_only=True)
class StorageState:
    """Normalisierter Zustand eines Batteriespeichers, herstellerunabhängig.

    `None` bedeutet „nicht verfügbar" (ungültige oder fehlgeschlagene Abfrage),
    `0` bedeutet eine gemessene Nullleistung — die beiden werden nie vermischt.
    """

    soc_percent: float | None
    charge_power_w: float | None
    discharge_power_w: float | None
    available: bool
    last_update: datetime
