"""Skytech HEMS Battery Provider — Setup und Unload der Integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .adapters.base import StorageAdapter
from .adapters.e3dc_rscp import E3dcRscpAdapter
from .adapters.marstek_udp import MarstekUdpAdapter
from .const import (
    CONF_HEMS_ENTITY_PREFIX,
    CONF_HEMS_TIMEOUT_FACTOR,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    CONF_RESPONSE_CHECK_MAX_ACTUAL,
    CONF_RESPONSE_CHECK_MIN_REQUEST,
    CONF_RESPONSE_CHECK_TIME,
    CONF_RSCP_KEY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_RESPONSE_CHECK_MAX_ACTUAL_W,
    DEFAULT_RESPONSE_CHECK_MIN_REQUEST_W,
    DEFAULT_RESPONSE_CHECK_TIME_SECONDS,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    MANUFACTURER_E3DC,
    MANUFACTURER_MARSTEK,
    PROTOCOL_E3DC_RSCP,
    PROTOCOL_MARSTEK_UDP,
)
from .coordinator import BatteryBridgeConfigEntry, BatteryBridgeCoordinator
from .heartbeat import DEFAULT_TIMEOUT_FACTOR
from .hems_bridge import HemsBridge
from .interface import get_interface
from .response_check import ResponseCheck

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: BatteryBridgeConfigEntry) -> bool:
    """Einen Speicher-Entry einrichten: Adapter bauen, Coordinator starten, Platforms laden."""
    adapter = _build_adapter(entry)
    update_interval_seconds = entry.options.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
    )
    coordinator = BatteryBridgeCoordinator(
        hass, entry, adapter, update_interval=timedelta(seconds=update_interval_seconds)
    )
    await coordinator.async_config_entry_first_refresh()

    hems_entity_prefix = entry.data.get(CONF_HEMS_ENTITY_PREFIX)
    if hems_entity_prefix:
        coordinator.hems_bridge = HemsBridge(
            coordinator,
            hems_entity_prefix,
            entry.options.get(CONF_HEMS_TIMEOUT_FACTOR, DEFAULT_TIMEOUT_FACTOR),
            _build_response_check(entry, adapter),
        )
        await coordinator.hems_bridge.async_setup()
        # Eine Schnittstellen-Entität für alle Speicher (D-019).
        get_interface(hass).register(hems_entity_prefix, coordinator)
    _remove_legacy_interface_sensor(hass, entry)

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: BatteryBridgeConfigEntry) -> None:
    """Options-Flow-Änderung (z. B. neues Abfrageintervall) wirkt sofort per Reload."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BatteryBridgeConfigEntry) -> bool:
    """Platforms entladen, die HEMS-Anbindung (falls aktiv) und den Adapter-Transport schließen."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = entry.runtime_data
        if coordinator.hems_bridge is not None:
            coordinator.hems_bridge.async_unload()
            get_interface(hass).unregister(entry.data[CONF_HEMS_ENTITY_PREFIX])
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
    if manufacturer == MANUFACTURER_E3DC and protocol == PROTOCOL_E3DC_RSCP:
        return E3dcRscpAdapter(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_RSCP_KEY],
        )
    raise ValueError(f"Unbekannter Hersteller/Protokoll: {manufacturer}/{protocol}")


def _build_response_check(
    entry: BatteryBridgeConfigEntry, adapter: StorageAdapter
) -> ResponseCheck | None:
    """Soll/Ist-Vergleich (D-018/D-019), nur wenn der Adapter ihn vorsieht (Marstek)."""
    if not adapter.response_check_supported:
        return None
    options = entry.options
    return ResponseCheck(
        name=entry.title,
        time_s=options.get(CONF_RESPONSE_CHECK_TIME, DEFAULT_RESPONSE_CHECK_TIME_SECONDS),
        min_request_w=options.get(
            CONF_RESPONSE_CHECK_MIN_REQUEST, DEFAULT_RESPONSE_CHECK_MIN_REQUEST_W
        ),
        max_actual_w=options.get(
            CONF_RESPONSE_CHECK_MAX_ACTUAL, DEFAULT_RESPONSE_CHECK_MAX_ACTUAL_W
        ),
    )


def _remove_legacy_interface_sensor(hass: HomeAssistant, entry: BatteryBridgeConfigEntry) -> None:
    """Den Schnittstellen-Sensor je Speicher aus 0.5.0/0.6.0 (D-017) aus der Registry entfernen.

    Seit D-019 gibt es nur noch `sensor.battery_provider_schnittstelle`; ohne Aufräumen bliebe die
    alte Entität als „nicht mehr bereitgestellt“ stehen.
    """
    registry = er.async_get(hass)
    device_id = entry.unique_id or entry.entry_id
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{device_id}_hems_schnittstelle")
    if entity_id is not None:
        registry.async_remove(entity_id)
