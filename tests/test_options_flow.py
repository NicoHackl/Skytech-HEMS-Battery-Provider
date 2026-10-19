"""Tests für den Options-Flow: Abfrageintervall nachträglich ändern (D-014)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.const import (
    CONF_RESPONSE_CHECK_MAX_ACTUAL,
    CONF_RESPONSE_CHECK_MIN_REQUEST,
    CONF_RESPONSE_CHECK_TIME,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
)
from custom_components.battery_bridge.models import StorageState
from tests.conftest import make_e3dc_entry, make_marstek_entry

# Defaults des Soll/Ist-Vergleichs, den der Options-Flow beim Marstek mitführt (D-018).
_RESPONSE_DEFAULTS = {
    CONF_RESPONSE_CHECK_TIME: 30,
    CONF_RESPONSE_CHECK_MIN_REQUEST: 100,
    CONF_RESPONSE_CHECK_MAX_ACTUAL: 20,
}

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
    assert result["data_schema"]({}) == {CONF_UPDATE_INTERVAL: 15, **_RESPONSE_DEFAULTS}


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
    assert entry.options == {CONF_UPDATE_INTERVAL: 2, **_RESPONSE_DEFAULTS}
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


async def test_options_flow_frist_faktor_nur_mit_hems_anbindung(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mit HEMS-Präfix zeigt der Options-Flow den Frist-Faktor des Lebenszeichens (D-016)."""
    from custom_components.battery_bridge.const import CONF_HEMS_TIMEOUT_FACTOR

    _mock_adapter(monkeypatch)
    monkeypatch.setattr(MarstekUdpAdapter, "write_charge_power", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "write_discharge_power", AsyncMock(return_value=None))
    entry = make_marstek_entry(hems_entity_prefix="acspeicher1")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["data_schema"]({})[CONF_HEMS_TIMEOUT_FACTOR] == 3

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL: 5, CONF_HEMS_TIMEOUT_FACTOR: 11}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HEMS_TIMEOUT_FACTOR: "invalid_hems_timeout_factor"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL: 5, CONF_HEMS_TIMEOUT_FACTOR: 4}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_HEMS_TIMEOUT_FACTOR] == 4


async def test_soll_ist_felder_nur_beim_marstek(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-018: der Vergleich ist vorerst nur für den Marstek vorgesehen."""
    from custom_components.battery_bridge.adapters.e3dc_rscp import E3dcRscpAdapter

    state = StorageState(
        soc_percent=50, charge_power_w=0, discharge_power_w=0, available=True,
        last_update=datetime.now(UTC),
    )
    monkeypatch.setattr(E3dcRscpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(E3dcRscpAdapter, "read", AsyncMock(return_value=state))
    monkeypatch.setattr(E3dcRscpAdapter, "close", AsyncMock(return_value=None))
    entry = make_e3dc_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["data_schema"]({}) == {CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS}


async def test_soll_ist_werte_landen_im_adapter(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_adapter(monkeypatch)
    entry = make_marstek_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {CONF_UPDATE_INTERVAL: 5, CONF_RESPONSE_CHECK_TIME: 45,
         CONF_RESPONSE_CHECK_MIN_REQUEST: 200, CONF_RESPONSE_CHECK_MAX_ACTUAL: 30},
    )
    await hass.async_block_till_done()

    check = entry.runtime_data.adapter._response_check
    assert (check.time_s, check.min_request_w, check.max_actual_w) == (45, 200, 30)
    assert check.max_step_s == 10


async def test_soll_ist_erkennungszeit_null_schaltet_ab(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_adapter(monkeypatch)
    entry = make_marstek_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {CONF_UPDATE_INTERVAL: 5, CONF_RESPONSE_CHECK_TIME: 0}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_RESPONSE_CHECK_TIME] == 0


@pytest.mark.parametrize(
    ("user_input", "field", "error"),
    [
        ({CONF_RESPONSE_CHECK_TIME: 5}, CONF_RESPONSE_CHECK_TIME,
         "invalid_response_check_time_seconds"),
        ({CONF_RESPONSE_CHECK_MIN_REQUEST: 10}, CONF_RESPONSE_CHECK_MIN_REQUEST,
         "invalid_response_check_min_request_w"),
        ({CONF_RESPONSE_CHECK_MIN_REQUEST: 100, CONF_RESPONSE_CHECK_MAX_ACTUAL: 100},
         CONF_RESPONSE_CHECK_MAX_ACTUAL, "response_check_actual_above_request"),
    ],
)
async def test_soll_ist_werte_werden_geprueft(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch,
    user_input: dict, field: str, error: str,
) -> None:
    _mock_adapter(monkeypatch)
    entry = make_marstek_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {CONF_UPDATE_INTERVAL: 5, **user_input}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {field: error}

