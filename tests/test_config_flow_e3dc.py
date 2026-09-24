"""Tests für den E3DC-Zweig des Config-Flows (D-015)."""

from __future__ import annotations

from unittest.mock import AsyncMock, PropertyMock

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.battery_bridge.adapters.base import (
    StorageAdapterAuthError,
    StorageAdapterError,
)
from custom_components.battery_bridge.adapters.e3dc_rscp import E3dcRscpAdapter
from custom_components.battery_bridge.const import (
    CONF_HEMS_ENTITY_PREFIX,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    CONF_RSCP_KEY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    MANUFACTURER_E3DC,
    PROTOCOL_E3DC_RSCP,
)
from tests.conftest import make_e3dc_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_INPUT = {
    CONF_HOST: "192.168.1.50",
    CONF_PORT: 5033,
    CONF_USERNAME: "benutzer@example.com",
    CONF_PASSWORD: "geheim",
    CONF_RSCP_KEY: "schluessel",
}


def _patch_adapter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    connect: AsyncMock | None = None,
    serial_number: str | None = "S10-123456",
) -> None:
    monkeypatch.setattr(E3dcRscpAdapter, "connect", connect or AsyncMock(return_value=None))
    monkeypatch.setattr(E3dcRscpAdapter, "read", AsyncMock(return_value=None))
    monkeypatch.setattr(E3dcRscpAdapter, "close", AsyncMock(return_value=None))
    monkeypatch.setattr(
        E3dcRscpAdapter, "serial_number", PropertyMock(return_value=serial_number)
    )


async def _start_e3dc_step(hass: HomeAssistant) -> dict:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MANUFACTURER: MANUFACTURER_E3DC}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "e3dc_rscp"
    return result


async def test_erfolgreicher_flow_legt_e3dc_entry_an(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verbindungstest ok → Entry mit Zugangsdaten, unique_id aus der Seriennummer."""
    _patch_adapter(monkeypatch)
    step = await _start_e3dc_step(hass)

    result = await hass.config_entries.flow.async_configure(
        step["flow_id"], {**_INPUT, CONF_HEMS_ENTITY_PREFIX: "e3dc"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "E3DC 192.168.1.50"
    assert result["data"] == {
        CONF_MANUFACTURER: MANUFACTURER_E3DC,
        CONF_PROTOCOL: PROTOCOL_E3DC_RSCP,
        **_INPUT,
        CONF_HEMS_ENTITY_PREFIX: "e3dc",
    }
    assert result["options"] == {CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS}
    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "e3dc_S10-123456"


async def test_ohne_seriennummer_faellt_unique_id_auf_adresse_zurueck(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Meldet das Gerät keine Seriennummer, dient Host+Port als Kennung."""
    _patch_adapter(monkeypatch, serial_number=None)
    step = await _start_e3dc_step(hass)

    await hass.config_entries.flow.async_configure(step["flow_id"], _INPUT)

    assert hass.config_entries.async_entries(DOMAIN)[0].unique_id == "e3dc_192.168.1.50:5033"


async def test_abgelehnte_zugangsdaten_zeigen_invalid_auth(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Falsche Zugangsdaten → eigener Hinweis, nicht „nicht erreichbar"."""
    _patch_adapter(
        monkeypatch, connect=AsyncMock(side_effect=StorageAdapterAuthError("abgelehnt"))
    )
    step = await _start_e3dc_step(hass)

    result = await hass.config_entries.flow.async_configure(step["flow_id"], _INPUT)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_nicht_erreichbar_zeigt_cannot_connect(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gerät antwortet nicht → `cannot_connect`, kein Entry."""
    _patch_adapter(monkeypatch, connect=AsyncMock(side_effect=StorageAdapterError("weg")))
    step = await _start_e3dc_step(hass)

    result = await hass.config_entries.flow.async_configure(step["flow_id"], _INPUT)

    assert result["errors"] == {"base": "cannot_connect"}


async def test_bereits_eingerichtetes_e3dc_bricht_ab(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dieselbe Seriennummer legt keinen zweiten Entry an — auch unter neuer IP."""
    _patch_adapter(monkeypatch)
    make_e3dc_entry().add_to_hass(hass)
    step = await _start_e3dc_step(hass)

    result = await hass.config_entries.flow.async_configure(step["flow_id"], _INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
