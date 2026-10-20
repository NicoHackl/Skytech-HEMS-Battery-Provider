"""Tests für sensor.battery_provider_schnittstelle (interface.py, D-019, Vertrag 2.0)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_bridge import hems_bridge
from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.e3dc_rscp import E3dcRscpAdapter
from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.const import DOMAIN
from custom_components.battery_bridge.interface import INTERFACE_ENTITY_ID
from custom_components.battery_bridge.models import StorageState
from tests.conftest import hems_zyklus, make_e3dc_entry, make_marstek_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


def _state(**overrides: object) -> StorageState:
    values: dict[str, object] = {
        "soc_percent": 12,
        "charge_power_w": 0,
        "discharge_power_w": 0,
        "available": True,
        "last_update": datetime.now(UTC),
    }
    values.update(overrides)
    return StorageState(**values)  # type: ignore[arg-type]


def _mock(monkeypatch: pytest.MonkeyPatch, adapter_cls: type, state: StorageState) -> AsyncMock:
    read = AsyncMock(return_value=state)
    monkeypatch.setattr(adapter_cls, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(adapter_cls, "read", read)
    monkeypatch.setattr(adapter_cls, "close", AsyncMock(return_value=None))
    monkeypatch.setattr(adapter_cls, "write_charge_power", AsyncMock(return_value=None))
    monkeypatch.setattr(adapter_cls, "write_discharge_power", AsyncMock(return_value=None))
    return read


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_ein_sensor_fuer_alle_speicher(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock(monkeypatch, MarstekUdpAdapter, _state())
    _mock(monkeypatch, E3dcRscpAdapter, _state(charge_allowed=True, discharge_allowed=True))
    await _setup(hass, make_marstek_entry(hems_entity_prefix="acspeicher1"))
    await _setup(hass, make_e3dc_entry(hems_entity_prefix="e3dc_speicher"))
    await _setup(hass, make_marstek_entry(host="127.0.0.9", hems_entity_prefix=None))

    sensor = hass.states.get(INTERFACE_ENTITY_ID)
    assert sensor.state == "acspeicher1,e3dc_speicher"  # ohne HEMS-Präfix nicht dabei
    attrs = sensor.attributes
    assert attrs["schnittstelle_version"] == 2
    for prefix in ("acspeicher1", "e3dc_speicher"):
        assert attrs[f"{prefix}_ladefreigabe"] is True
        assert attrs[f"{prefix}_entladefreigabe"] is True
        assert attrs[f"{prefix}_ladesperrgrund"] is None
        assert attrs[f"{prefix}_entladesperrgrund"] is None
    # Keine Sensoren je Speicher mehr
    assert not [
        s for s in hass.states.async_entity_ids("sensor") if s.endswith("_hems_schnittstelle")
    ]


async def test_geraetesperre_mit_grund(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock(
        monkeypatch,
        E3dcRscpAdapter,
        _state(charge_allowed=True, discharge_allowed=False, lock_reasons=("notstromreserve",)),
    )
    await _setup(hass, make_e3dc_entry(hems_entity_prefix="e3dc_speicher"))

    attrs = hass.states.get(INTERFACE_ENTITY_ID).attributes
    assert attrs["e3dc_speicher_ladefreigabe"] is True
    assert attrs["e3dc_speicher_entladefreigabe"] is False
    assert attrs["e3dc_speicher_entladesperrgrund"] == "notstromreserve"


async def test_nicht_erreichbar_sperrt_beide_richtungen(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    read = _mock(monkeypatch, MarstekUdpAdapter, _state())
    entry = await _setup(hass, make_marstek_entry(hems_entity_prefix="acspeicher1"))
    read.side_effect = StorageAdapterError("keine Antwort")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    attrs = hass.states.get(INTERFACE_ENTITY_ID).attributes
    assert attrs["acspeicher1_ladefreigabe"] is False
    assert attrs["acspeicher1_entladefreigabe"] is False
    assert attrs["acspeicher1_ladesperrgrund"] == "nicht_erreichbar"
    assert attrs["acspeicher1_entladesperrgrund"] == "nicht_erreichbar"


async def test_soll_ist_sperre_mit_hems_istwerten(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Vorfall 19.10.2026 durchgespielt: Entladung bestätigt gesendet, HEMS misst 0 W."""
    now = [1000.0]
    monkeypatch.setattr(hems_bridge.time, "monotonic", lambda: now[0])
    read = _mock(
        monkeypatch, MarstekUdpAdapter, _state(charge_allowed=True, discharge_allowed=True)
    )
    entry = await _setup(hass, make_marstek_entry(hems_entity_prefix="acspeicher1"))
    await hems_zyklus(hass, interval_s=5)
    hass.states.async_set("input_number.ems_acspeicher1_anforderung_leistung_w", "-528")
    hass.states.async_set("input_select.ems_acspeicher1_anforderung_betriebsart", "entladen")
    await hass.async_block_till_done()

    for _ in range(7):
        now[0] += 5
        await hems_zyklus(
            hass, interval_s=5, acspeicher1_ladeleistung=0, acspeicher1_entladeleistung=0
        )

    attrs = hass.states.get(INTERFACE_ENTITY_ID).attributes
    assert attrs["acspeicher1_entladefreigabe"] is False
    assert attrs["acspeicher1_entladesperrgrund"] == "keine_reaktion_entladen"
    assert attrs["acspeicher1_sperre_bis_soc_prozent"] == 13
    assert attrs["acspeicher1_ladefreigabe"] is True

    # SoC +1 %: wieder frei
    read.return_value = _state(soc_percent=13, charge_allowed=True, discharge_allowed=True)
    await entry.runtime_data.async_refresh()
    now[0] += 5
    await hems_zyklus(
        hass, interval_s=5, acspeicher1_ladeleistung=300, acspeicher1_entladeleistung=0
    )

    attrs = hass.states.get(INTERFACE_ENTITY_ID).attributes
    assert attrs["acspeicher1_entladefreigabe"] is True
    assert "acspeicher1_sperre_bis_soc_prozent" not in attrs


async def test_e3dc_ohne_soll_ist_vergleich(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock(monkeypatch, E3dcRscpAdapter, _state())
    entry = await _setup(hass, make_e3dc_entry(hems_entity_prefix="e3dc_speicher"))
    assert entry.runtime_data.hems_bridge.response_check is None


async def test_unload_entfernt_speicher_und_zuletzt_den_sensor(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock(monkeypatch, MarstekUdpAdapter, _state())
    _mock(monkeypatch, E3dcRscpAdapter, _state())
    marstek = await _setup(hass, make_marstek_entry(hems_entity_prefix="acspeicher1"))
    e3dc = await _setup(hass, make_e3dc_entry(hems_entity_prefix="e3dc_speicher"))

    assert await hass.config_entries.async_unload(marstek.entry_id)
    await hass.async_block_till_done()
    sensor = hass.states.get(INTERFACE_ENTITY_ID)
    assert sensor.state == "e3dc_speicher"
    assert "acspeicher1_ladefreigabe" not in sensor.attributes

    assert await hass.config_entries.async_unload(e3dc.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(INTERFACE_ENTITY_ID) is None


async def test_alter_sensor_je_speicher_wird_aus_der_registry_entfernt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock(monkeypatch, MarstekUdpAdapter, _state())
    entry = make_marstek_entry(hems_entity_prefix="acspeicher1")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "sensor", DOMAIN, f"{entry.unique_id}_hems_schnittstelle", config_entry=entry
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(old.entity_id) is None
