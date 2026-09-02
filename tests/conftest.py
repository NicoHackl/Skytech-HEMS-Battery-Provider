"""Gemeinsame Test-Helfer für Coordinator-, Number- und Config-Flow-Tests."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_bridge.const import (
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    DOMAIN,
    MANUFACTURER_MARSTEK,
    PROTOCOL_MARSTEK_UDP,
)


def make_marstek_entry(
    *, host: str = "127.0.0.1", port: int = 30000, title: str = "Marstek 127.0.0.1"
) -> MockConfigEntry:
    """Ein `MockConfigEntry`, wie ihn der echte Config-Flow für Marstek/UDP anlegen würde."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{host}:{port}",
        title=title,
        data={
            CONF_MANUFACTURER: MANUFACTURER_MARSTEK,
            CONF_PROTOCOL: PROTOCOL_MARSTEK_UDP,
            CONF_HOST: host,
            CONF_PORT: port,
        },
    )


def entity_ids_by_key(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, str]:
    """Entity-IDs des Entry, keyed nach dem EntityDescription-`key` (`soc`, `ist_ladeleistung`,
    `soll_ladeleistung`, …) — nicht nach dem letzten `_`-Teil: `ist_ladeleistung` und
    `soll_ladeleistung` enden beide auf „ladeleistung", ein Rsplit würde sie verwechseln.
    """
    registry = er.async_get(hass)
    device_id = entry.unique_id or entry.entry_id
    prefix = f"{device_id}_"
    return {
        entry_.unique_id.removeprefix(prefix): entry_.entity_id
        for entry_ in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
