"""Skytech HEMS Battery Provider — Setup und Unload der Integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .adapters.base import StorageAdapter
from .adapters.marstek_udp import MarstekUdpAdapter
from .const import (
    CONF_HEMS_ENTITY_PREFIX,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    MANUFACTURER_MARSTEK,
    PROTOCOL_MARSTEK_UDP,
)
from .coordinator import BatteryBridgeConfigEntry, BatteryBridgeCoordinator
from .hems_bridge import HemsBridge

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: BatteryBridgeConfigEntry) -> bool:
    """Einen Speicher-Entry einrichten: Adapter bauen, Coordinator starten, Platforms laden."""
    adapter = _build_adapter(entry)
    coordinator = BatteryBridgeCoordinator(hass, entry, adapter)
    await coordinator.async_config_entry_first_refresh()

    hems_entity_prefix = entry.data.get(CONF_HEMS_ENTITY_PREFIX)
    if hems_entity_prefix:
        coordinator.hems_bridge = HemsBridge(coordinator, hems_entity_prefix)
        await coordinator.hems_bridge.async_setup()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BatteryBridgeConfigEntry) -> bool:
    """Platforms entladen, die HEMS-Anbindung (falls aktiv) und den Adapter-Transport schließen."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        if coordinator.hems_bridge is not None:
            coordinator.hems_bridge.async_unload()
        await coordinator.adapter.close()
    return unloaded


def _build_adapter(entry: BatteryBridgeConfigEntry) -> StorageAdapter:
    """Adapter aus Hersteller/Protokoll der ConfigEntry erzeugen.

    Einzige Stelle, die Hersteller/Protokoll auf eine Adapter-Klasse abbildet — ein neuer
    Adapter (D-006: Hersteller × Protokoll) ergänzt hier einen weiteren Fall, ändert aber
    nichts an Coordinator oder Platforms (Invariante 1, docs/architektur.md).
    """
    manufacturer = entry.data[CONF_MANUFACTURER]
    protocol = entry.data[CONF_PROTOCOL]
    if manufacturer == MANUFACTURER_MARSTEK and protocol == PROTOCOL_MARSTEK_UDP:
        return MarstekUdpAdapter(entry.data[CONF_HOST], entry.data[CONF_PORT])
    raise ValueError(f"Unbekannter Hersteller/Protokoll: {manufacturer}/{protocol}")
