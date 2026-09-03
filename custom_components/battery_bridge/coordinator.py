"""Coordinator — fragt einen `StorageAdapter` im festen Intervall ab."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .adapters.base import StorageAdapter, StorageAdapterError
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .models import StorageState

if TYPE_CHECKING:
    from .hems_bridge import HemsBridge

_LOGGER = logging.getLogger(__name__)

type BatteryBridgeConfigEntry = ConfigEntry["BatteryBridgeCoordinator"]


class BatteryBridgeCoordinator(DataUpdateCoordinator[StorageState]):
    """Fragt einen `StorageAdapter` im festen Intervall ab und verteilt `StorageState`.

    Kennt nur das `StorageAdapter`-Protocol, nie Herstellerdetails — Invariante 1 in
    docs/architektur.md.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BatteryBridgeConfigEntry,
        adapter: StorageAdapter,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} ({entry.title})",
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.adapter = adapter
        # Nur gesetzt, wenn der Entry ein HEMS-Präfix konfiguriert hat — siehe __init__.py und
        # hems_bridge.py (D-009). Ohne HEMS-Anbindung bleibt dieses Feld `None`.
        self.hems_bridge: HemsBridge | None = None

    async def _async_setup(self) -> None:
        """Verbindung einmalig vor dem ersten Poll aufbauen.

        Schlägt sie fehl, versucht Home Assistant den Entry-Start automatisch erneut
        (`ConfigEntryNotReady`) — kein Absturz, siehe docs/architektur.md Abschnitt Polling.
        """
        try:
            await self.adapter.connect()
        except StorageAdapterError as exc:
            raise ConfigEntryNotReady(str(exc)) from exc

    async def _async_update_data(self) -> StorageState:
        try:
            return await self.adapter.read()
        except StorageAdapterError as exc:
            raise UpdateFailed(str(exc)) from exc
