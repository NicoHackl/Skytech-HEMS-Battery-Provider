"""Tests für die Lese-Sensoren: SoC, Ist-Leistung, und die bedingten HEMS-Soll-Sensoren."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.models import StorageState
from tests.conftest import entity_ids_by_key, make_marstek_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_PREFIX = "acspeicher1"
_POWER_ENTITY = f"input_number.ems_{_PREFIX}_anforderung_leistung_w"
_MODE_ENTITY = f"input_select.ems_{_PREFIX}_anforderung_betriebsart"


async def _setup_loaded_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    *,
    hems_entity_prefix: str | None = None,
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
    monkeypatch.setattr(MarstekUdpAdapter, "write_charge_power", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "write_discharge_power", AsyncMock(return_value=None))

    entry = make_marstek_entry(hems_entity_prefix=hems_entity_prefix)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    return entry, entity_ids_by_key(hass, entry)


async def _set_anforderung(hass: HomeAssistant, *, leistung_w: str, betriebsart: str) -> None:
    """Wie in test_hems_bridge.py: Leistung zuerst, Betriebsart danach — genau ein sauberer Sync."""
    hass.states.async_set(_POWER_ENTITY, leistung_w)
    await hass.async_block_till_done()
    hass.states.async_set(_MODE_ENTITY, betriebsart)
    await hass.async_block_till_done()


async def test_bestehende_sensoren_unveraendert_durch_hems_erweiterung(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: SoC/Ist-Lade-/Ist-Entladeleistung funktionieren unverändert, auch ohne
    HEMS-Präfix — der Umbau von async_setup_entry() auf eine Liste darf daran nichts ändern."""
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch)

    assert hass.states.get(entity_ids["soc"]).state == "50"
    assert hass.states.get(entity_ids["ist_ladeleistung"]).state == "0"
    assert hass.states.get(entity_ids["ist_entladeleistung"]).state == "0"


async def test_hems_sensoren_werden_nur_mit_hems_praefix_angelegt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne HEMS-Präfix gäbe es nie einen Wert dafür — die Entities sollen dann gar nicht erst
    existieren, statt dauerhaft `unavailable` herumzustehen."""
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch, hems_entity_prefix=None)

    assert "hems_soll_ladeleistung" not in entity_ids
    assert "hems_soll_entladeleistung" not in entity_ids


async def test_hems_sensoren_nicht_verfuegbar_vor_erstem_sync(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HEMS-Präfix gesetzt, aber die HEMS-Helfer existieren (noch) nicht → kein erfolgreicher
    Sync bisher → beide Sensoren `unavailable`, kein geratener Ersatzwert."""
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch, hems_entity_prefix=_PREFIX)

    assert hass.states.get(entity_ids["hems_soll_ladeleistung"]).state == "unavailable"
    assert hass.states.get(entity_ids["hems_soll_entladeleistung"]).state == "unavailable"


async def test_hems_soll_ladeleistung_zeigt_gesendeten_wert(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch, hems_entity_prefix=_PREFIX)

    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")

    assert hass.states.get(entity_ids["hems_soll_ladeleistung"]).state == "800.0"
    assert hass.states.get(entity_ids["hems_soll_entladeleistung"]).state == "0.0"


async def test_hems_soll_entladeleistung_zeigt_gesendeten_wert(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch, hems_entity_prefix=_PREFIX)

    await _set_anforderung(hass, leistung_w="-500", betriebsart="entladen")

    assert hass.states.get(entity_ids["hems_soll_ladeleistung"]).state == "0.0"
    assert hass.states.get(entity_ids["hems_soll_entladeleistung"]).state == "500.0"
