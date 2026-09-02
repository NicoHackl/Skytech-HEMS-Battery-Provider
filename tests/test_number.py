"""Tests für die Soll-Leistungs-Entities: Schreiben, Fehler melden, Refresh anstoßen."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.models import StorageState
from tests.conftest import entity_ids_by_key, make_marstek_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _setup_loaded_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> tuple[MockConfigEntry, dict[str, str]]:
    state = StorageState(
        soc_percent=50,
        charge_power_w=0,
        discharge_power_w=0,
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

    return entry, entity_ids_by_key(hass, entry)


async def test_soll_ladeleistung_setzen_ruft_adapter_und_aktualisiert_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erfolgreicher Schreibvorgang: Adapter bekommt den Wert, Entity übernimmt ihn als state."""
    write_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(MarstekUdpAdapter, "write_charge_power", write_mock)
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch)

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_ids["soll_ladeleistung"], "value": 500},
        blocking=True,
    )

    write_mock.assert_awaited_once_with(500.0)
    assert hass.states.get(entity_ids["soll_ladeleistung"]).state == "500.0"


async def test_soll_entladeleistung_fehler_wird_nicht_still_geschluckt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lehnt das Gerät den Sollwert ab, meldet HA das als Fehler statt eines stillen Erfolgs."""
    monkeypatch.setattr(
        MarstekUdpAdapter,
        "write_discharge_power",
        AsyncMock(side_effect=StorageAdapterError("abgelehnt")),
    )
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_ids["soll_entladeleistung"], "value": 750},
            blocking=True,
        )

    # Fehlgeschlagener Schreibvorgang darf den zuletzt bekannten Stand nicht überschreiben.
    assert hass.states.get(entity_ids["soll_entladeleistung"]).state == "0.0"
