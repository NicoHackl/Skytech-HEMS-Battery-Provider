"""Tests für Setup/Coordinator: Entry laden, Sensoren befüllen, Fehler übersetzen."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.models import StorageState
from tests.conftest import entity_ids_by_key, make_marstek_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_setup_entry_befuellt_sensoren_aus_storage_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erfolgreicher Poll: alle drei Sensoren zeigen die Werte aus dem StorageState."""
    state = StorageState(
        soc_percent=42,
        charge_power_w=0,
        discharge_power_w=150,
        available=True,
        last_update=datetime.now(UTC),
    )
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", AsyncMock(return_value=state))
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))

    entry = make_marstek_entry()
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data is state

    entity_ids = entity_ids_by_key(hass, entry)
    assert hass.states.get(entity_ids["soc"]).state == "42"
    assert hass.states.get(entity_ids["ist_ladeleistung"]).state == "0"
    assert hass.states.get(entity_ids["ist_entladeleistung"]).state == "150"


async def test_setup_entry_bei_verbindungsfehler_geht_in_retry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nicht erreichbares Gerät beim Start → SETUP_RETRY, kein Absturz (Plan Abschnitt 7)."""
    monkeypatch.setattr(
        MarstekUdpAdapter,
        "connect",
        AsyncMock(side_effect=StorageAdapterError("nicht erreichbar")),
    )

    entry = make_marstek_entry()
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_poll_fehler_setzt_sensoren_auf_unavailable(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fehlgeschlagener Poll nach erfolgreichem Start → Entities `unavailable`, kein Reload."""
    state = StorageState(
        soc_percent=10,
        charge_power_w=0,
        discharge_power_w=0,
        available=True,
        last_update=datetime.now(UTC),
    )
    read_mock = AsyncMock(return_value=state)
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", read_mock)
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))

    entry = make_marstek_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    read_mock.side_effect = StorageAdapterError("Timeout")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert entry.runtime_data.last_update_success is False
    entity_ids = entity_ids_by_key(hass, entry)
    assert hass.states.get(entity_ids["soc"]).state == STATE_UNAVAILABLE
