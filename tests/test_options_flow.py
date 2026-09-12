"""Tests für den Options-Flow: Abfrageintervall nachträglich ändern (D-014)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
)
from custom_components.battery_bridge.models import StorageState
from tests.conftest import make_marstek_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _mock_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    state = StorageState(
        soc_percent=10,
        charge_power_w=0,
        discharge_power_w=0,
        available=True,
        last_update=datetime.now(UTC),
    )
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", AsyncMock(return_value=state))
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))


async def test_options_flow_zeigt_aktuellen_wert_als_default(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Formular zeigt das aktuell konfigurierte Intervall, nicht den globalen Default."""
    _mock_adapter(monkeypatch)
    entry = make_marstek_entry(update_interval_seconds=15)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["data_schema"]({}) == {CONF_UPDATE_INTERVAL: 15}


async def test_options_flow_aendert_intervall_und_laedt_entry_sofort_neu(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neuer Wert landet in `entry.options`, der Entry wird ohne HA-Neustart neu geladen und der
    Coordinator übernimmt sofort den neuen Takt.
    """
    _mock_adapter(monkeypatch)
    entry = make_marstek_entry(update_interval_seconds=DEFAULT_UPDATE_INTERVAL_SECONDS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {CONF_UPDATE_INTERVAL: 2}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_UPDATE_INTERVAL: 2}
    assert entry.runtime_data.update_interval == timedelta(seconds=2)


async def test_options_flow_lehnt_wert_ausserhalb_bereich_ab(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wert außerhalb 1–60 s wird abgelehnt, `entry.options` bleibt unverändert."""
    _mock_adapter(monkeypatch)
    entry = make_marstek_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {CONF_UPDATE_INTERVAL: 0}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_UPDATE_INTERVAL: "invalid_update_interval"}
    assert entry.options == {CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS}
