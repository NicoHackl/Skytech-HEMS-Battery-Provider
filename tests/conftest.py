"""Gemeinsame Test-Helfer für Coordinator-, Number- und Config-Flow-Tests."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_bridge.const import (
    CONF_HEMS_ENTITY_PREFIX,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    CONF_RSCP_KEY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    E3DC_RSCP_DEFAULT_PORT,
    MANUFACTURER_E3DC,
    MANUFACTURER_MARSTEK,
    PROTOCOL_E3DC_RSCP,
    PROTOCOL_MARSTEK_UDP,
)


def make_marstek_entry(
    *,
    host: str = "127.0.0.1",
    port: int = 30000,
    title: str = "Marstek 127.0.0.1",
    hems_entity_prefix: str | None = None,
    update_interval_seconds: int = DEFAULT_UPDATE_INTERVAL_SECONDS,
) -> MockConfigEntry:
    """Ein `MockConfigEntry`, wie ihn der echte Config-Flow für Marstek/UDP anlegen würde.

    `hems_entity_prefix` entspricht dem gleichnamigen, optionalen Config-Flow-Feld — gesetzt,
    wenn ein Test die eingebaute HEMS-Anbindung (hems_bridge.py) mit einrichten soll.
    `update_interval_seconds` landet in `entry.options`, nicht `entry.data` — genau wie beim
    echten Config- und Options-Flow (D-014).
    """
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{host}:{port}",
        title=title,
        data={
            CONF_MANUFACTURER: MANUFACTURER_MARSTEK,
            CONF_PROTOCOL: PROTOCOL_MARSTEK_UDP,
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_HEMS_ENTITY_PREFIX: hems_entity_prefix,
        },
        options={CONF_UPDATE_INTERVAL: update_interval_seconds},
    )


def make_e3dc_entry(
    *,
    host: str = "127.0.0.2",
    title: str = "E3DC 127.0.0.2",
    hems_entity_prefix: str | None = None,
    update_interval_seconds: int = DEFAULT_UPDATE_INTERVAL_SECONDS,
) -> MockConfigEntry:
    """Ein `MockConfigEntry`, wie ihn der echte Config-Flow für E3DC/RSCP anlegen würde (D-015)."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="e3dc_S10-123456",
        title=title,
        data={
            CONF_MANUFACTURER: MANUFACTURER_E3DC,
            CONF_PROTOCOL: PROTOCOL_E3DC_RSCP,
            CONF_HOST: host,
            CONF_PORT: E3DC_RSCP_DEFAULT_PORT,
            CONF_USERNAME: "benutzer@example.com",
            CONF_PASSWORD: "geheim",
            CONF_RSCP_KEY: "schluessel",
            CONF_HEMS_ENTITY_PREFIX: hems_entity_prefix,
        },
        options={CONF_UPDATE_INTERVAL: update_interval_seconds},
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


_hems_counter = 0


async def hems_zyklus(hass: HomeAssistant, interval_s: float = 30) -> None:
    """Einen SkytechHEMS-Zyklus simulieren: das Lebenszeichen ändert seinen Zähler (D-016)."""
    global _hems_counter
    _hems_counter += 1
    hass.states.async_set(
        "sensor.skytech_hems_status",
        str(_hems_counter),
        {"zyklus_zaehler": _hems_counter, "zyklus_intervall_s": interval_s},
    )
    await hass.async_block_till_done()
