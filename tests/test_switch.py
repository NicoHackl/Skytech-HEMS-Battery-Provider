"""Tests für den HEMS-Steuerung-Schalter (switch.py, D-011)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.models import StorageState
from tests.conftest import entity_ids_by_key, make_marstek_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_PREFIX = "acspeicher1"
_POWER_ENTITY = f"input_number.ems_{_PREFIX}_anforderung_leistung_w"
_MODE_ENTITY = f"input_select.ems_{_PREFIX}_anforderung_betriebsart"


async def _setup_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    *,
    hems_entity_prefix: str | None = _PREFIX,
) -> tuple[list[tuple[str, float]], dict[str, str]]:
    """Entry einrichten, alle Adapter-Schreibaufrufe in Reihenfolge aufzeichnen — wie in
    test_hems_bridge.py, hier bewusst dupliziert statt in conftest.py verschoben."""
    calls: list[tuple[str, float]] = []

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
    monkeypatch.setattr(
        MarstekUdpAdapter,
        "write_charge_power",
        AsyncMock(side_effect=lambda watts: calls.append(("charge", watts))),
    )
    monkeypatch.setattr(
        MarstekUdpAdapter,
        "write_discharge_power",
        AsyncMock(side_effect=lambda watts: calls.append(("discharge", watts))),
    )

    entry = make_marstek_entry(hems_entity_prefix=hems_entity_prefix)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    return calls, entity_ids_by_key(hass, entry)


async def _set_anforderung(hass: HomeAssistant, *, leistung_w: str, betriebsart: str) -> None:
    hass.states.async_set(_POWER_ENTITY, leistung_w)
    await hass.async_block_till_done()
    hass.states.async_set(_MODE_ENTITY, betriebsart)
    await hass.async_block_till_done()


async def _turn(hass: HomeAssistant, entity_id: str, *, on: bool) -> None:
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )


async def test_switch_wird_nur_mit_hems_praefix_angelegt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _calls, entity_ids = await _setup_entry(hass, monkeypatch, hems_entity_prefix=None)

    assert "hems_steuerung_aktiv" not in entity_ids


async def test_switch_wird_mit_hems_praefix_angelegt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _calls, entity_ids = await _setup_entry(hass, monkeypatch)

    assert "hems_steuerung_aktiv" in entity_ids


async def test_switch_ist_nach_setup_standardmaessig_ein(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _calls, entity_ids = await _setup_entry(hass, monkeypatch)

    assert hass.states.get(entity_ids["hems_steuerung_aktiv"]).state == "on"


async def test_ausschalten_stoppt_automatische_schreibvorgaenge(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls, entity_ids = await _setup_entry(hass, monkeypatch)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    calls.clear()

    await _turn(hass, entity_ids["hems_steuerung_aktiv"], on=False)
    await _set_anforderung(hass, leistung_w="500", betriebsart="entladen")

    assert calls == []
    assert hass.states.get(entity_ids["hems_steuerung_aktiv"]).state == "off"


async def test_einschalten_synchronisiert_sofort_mit_aktuellem_hems_wert(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wiedereinschalten darf nicht auf die nächste zufällige HEMS-Änderung warten."""
    calls, entity_ids = await _setup_entry(hass, monkeypatch)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    await _turn(hass, entity_ids["hems_steuerung_aktiv"], on=False)
    calls.clear()

    await _turn(hass, entity_ids["hems_steuerung_aktiv"], on=True)

    assert calls == [("discharge", 0.0), ("charge", 800.0)]
    assert hass.states.get(entity_ids["hems_steuerung_aktiv"]).state == "on"


async def test_ausgeschaltet_erlaubt_manuelles_setzen_der_soll_leistung(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der eigentliche Anwendungsfall: bei ausgeschalteter HEMS-Steuerung kommt ein manueller
    number.set_value ungestört beim Adapter an, ohne dass ein HEMS-Zyklus dazwischenfunkt."""
    calls, entity_ids = await _setup_entry(hass, monkeypatch)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    await _turn(hass, entity_ids["hems_steuerung_aktiv"], on=False)
    calls.clear()

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entity_ids["soll_entladeleistung"], "value": 250},
        blocking=True,
    )

    assert calls == [("discharge", 250.0)]
