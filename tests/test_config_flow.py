"""Tests für den Config-Flow: Hersteller wählen, Verbindungsdaten, Verbindungstest."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.const import (
    CONF_DISPLAY_NAME,
    CONF_HEMS_ENTITY_PREFIX,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    DOMAIN,
    MANUFACTURER_MARSTEK,
    PROTOCOL_MARSTEK_UDP,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _start_marstek_step(hass: HomeAssistant) -> dict:
    """Schritt 1 (Hersteller) durchlaufen und beim marstek_udp-Formular ankommen."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MANUFACTURER: MANUFACTURER_MARSTEK}
    )


async def test_erfolgreicher_flow_legt_entry_mit_verbindungsdaten_an(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erfolgreicher Verbindungstest → Entry mit Hersteller/Protokoll/Host/Port, korrekter
    unique_id.
    """
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))

    marstek_step = await _start_marstek_step(hass)
    assert marstek_step["type"] is FlowResultType.FORM
    assert marstek_step["step_id"] == "marstek_udp"

    result = await hass.config_entries.flow.async_configure(
        marstek_step["flow_id"],
        {CONF_DISPLAY_NAME: "Keller-Speicher", CONF_HOST: "192.168.1.42", CONF_PORT: 30000},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Keller-Speicher"
    assert result["data"] == {
        CONF_MANUFACTURER: MANUFACTURER_MARSTEK,
        CONF_PROTOCOL: PROTOCOL_MARSTEK_UDP,
        CONF_HOST: "192.168.1.42",
        CONF_PORT: 30000,
        CONF_HEMS_ENTITY_PREFIX: None,
    }
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "192.168.1.42:30000"


async def test_hems_praefix_wird_in_den_entry_uebernommen(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein angegebenes HEMS-Präfix landet unverändert in `entry.data` (aktiviert hems_bridge.py)."""
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))

    marstek_step = await _start_marstek_step(hass)
    result = await hass.config_entries.flow.async_configure(
        marstek_step["flow_id"],
        {
            CONF_HOST: "192.168.1.42",
            CONF_PORT: 30000,
            CONF_HEMS_ENTITY_PREFIX: "acspeicher1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HEMS_ENTITY_PREFIX] == "acspeicher1"


async def test_ohne_anzeigename_faellt_titel_auf_marstek_host_zurueck(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kein Anzeigename angegeben → Titel „Marstek <Host>" statt eines leeren Titels."""
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))

    marstek_step = await _start_marstek_step(hass)
    result = await hass.config_entries.flow.async_configure(
        marstek_step["flow_id"], {CONF_HOST: "192.168.1.50", CONF_PORT: 30000}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Marstek 192.168.1.50"


async def test_verbindungsfehler_zeigt_formular_mit_fehler_statt_absturz(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fehlgeschlagener Verbindungstest → Formular bleibt mit `cannot_connect`, kein Entry."""
    monkeypatch.setattr(
        MarstekUdpAdapter,
        "connect",
        AsyncMock(side_effect=StorageAdapterError("nicht erreichbar")),
    )
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))

    marstek_step = await _start_marstek_step(hass)
    result = await hass.config_entries.flow.async_configure(
        marstek_step["flow_id"], {CONF_HOST: "10.0.0.99", CONF_PORT: 30000}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "marstek_udp"
    assert result["errors"] == {"base": "cannot_connect"}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_bereits_eingerichteter_speicher_bricht_ab(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Host+Port, die schon einen Entry haben, legen keinen zweiten an (Plan Abschnitt 6)."""
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))

    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.168.1.42:30000",
        data={
            CONF_MANUFACTURER: MANUFACTURER_MARSTEK,
            CONF_PROTOCOL: PROTOCOL_MARSTEK_UDP,
            CONF_HOST: "192.168.1.42",
            CONF_PORT: 30000,
        },
    )
    existing.add_to_hass(hass)

    marstek_step = await _start_marstek_step(hass)
    result = await hass.config_entries.flow.async_configure(
        marstek_step["flow_id"], {CONF_HOST: "192.168.1.42", CONF_PORT: 30000}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
