"""Tests für die Lese-Sensoren: SoC, Ist-Leistung, und die bedingten HEMS-Soll-Sensoren."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.models import StorageState
from tests.conftest import entity_ids_by_key, hems_zyklus, make_marstek_entry

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
    if hems_entity_prefix:
        await hems_zyklus(hass)  # frischer HEMS-Zyklus nach dem Start (D-016)
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


async def test_hems_sensoren_zeigen_null_nach_start_ohne_helfer(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HEMS-Präfix gesetzt, HEMS-Helfer fehlen noch: beim Start ging der Speicher mangels frischem
    HEMS-Zyklus erfolgreich auf 0 (D-016) — die Sensoren zeigen genau diesen gesendeten Wert."""
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch, hems_entity_prefix=_PREFIX)

    assert hass.states.get(entity_ids["hems_soll_ladeleistung"]).state == "0.0"
    assert hass.states.get(entity_ids["hems_soll_entladeleistung"]).state == "0.0"


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


async def test_hems_sensoren_sind_bei_schreibfehler_nicht_verfuegbar(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erreicht der Sollwert das Gerät nicht mehr, ist unbekannt, was am Speicher gilt. Dann
    verschwindet der Wert, statt einen unbestätigten Stand weiterzuzeigen — am 10.09.2026 stand
    hier 96 Minuten lang unverändert `0.0`, während kein Schreibvorgang durchkam."""
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch, hems_entity_prefix=_PREFIX)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    assert hass.states.get(entity_ids["hems_soll_ladeleistung"]).state == "800.0"

    monkeypatch.setattr(
        MarstekUdpAdapter,
        "write_charge_power",
        AsyncMock(side_effect=StorageAdapterError("Gerät antwortet nicht")),
    )
    hass.states.async_set(_POWER_ENTITY, "801")
    await hass.async_block_till_done()

    assert hass.states.get(entity_ids["hems_soll_ladeleistung"]).state == "unavailable"
    assert hass.states.get(entity_ids["hems_soll_entladeleistung"]).state == "unavailable"



async def _setup_with_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, state: StorageState
) -> tuple[MockConfigEntry, dict[str, str]]:
    """Wie `_setup_loaded_entry()` mit HEMS-Präfix, aber mit frei wählbarem Gerätezustand."""
    monkeypatch.setattr(MarstekUdpAdapter, "connect", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "read", AsyncMock(return_value=state))
    monkeypatch.setattr(MarstekUdpAdapter, "close", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "write_charge_power", AsyncMock(return_value=None))
    monkeypatch.setattr(MarstekUdpAdapter, "write_discharge_power", AsyncMock(return_value=None))
    entry = make_marstek_entry(hems_entity_prefix=_PREFIX)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hems_zyklus(hass)
    return entry, entity_ids_by_key(hass, entry)


def _state(**overrides: object) -> StorageState:
    values: dict[str, object] = {
        "soc_percent": 14,
        "charge_power_w": 300,
        "discharge_power_w": 0,
        "available": True,
        "last_update": datetime(2026, 10, 18, 7, 1, 39, tzinfo=UTC),
    }
    values.update(overrides)
    return StorageState(**values)  # type: ignore[arg-type]


async def test_schnittstellen_sensor_nur_mit_hems_praefix(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    _entry, entity_ids = await _setup_loaded_entry(hass, monkeypatch, hems_entity_prefix=None)

    assert "hems_schnittstelle" not in entity_ids


async def test_schnittstellen_sensor_bereit_mit_allen_attributen(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-017: Messwerte, Freigaben und Spiegel der HEMS-Anforderung an einer Stelle."""
    _entry, entity_ids = await _setup_with_state(
        hass,
        monkeypatch,
        _state(charge_allowed=True, discharge_allowed=True, temperature_c=21.0),
    )
    await _set_anforderung(hass, leistung_w="-2256", betriebsart="entladen")

    sensor = hass.states.get(entity_ids["hems_schnittstelle"])
    assert sensor.state == "bereit"
    attrs = sensor.attributes
    assert attrs["schnittstelle_version"] == 1
    assert attrs["messung_ok"] is True
    assert attrs["gemessen_am"] == "18.10.2026 09:01:39"
    assert attrs["soc_prozent"] == 14
    assert attrs["ist_ladeleistung_w"] == 300
    assert attrs["ist_entladeleistung_w"] == 0
    assert attrs["laden_freigegeben"] is True
    assert attrs["entladen_freigegeben"] is True
    assert attrs["sperrgruende"] == []
    assert attrs["batterietemperatur_c"] == 21.0
    assert attrs["hems_anforderung_w"] == -2256
    assert attrs["hems_anforderung_betriebsart"] == "entladen"
    assert attrs["gesendet_ladeleistung_w"] == 0
    assert attrs["gesendet_entladeleistung_w"] == 2256
    assert attrs["senden_ok"] is True
    assert attrs["hems_lebenszeichen"] is True
    assert attrs["hems_steuerung_aktiv"] is True


@pytest.mark.parametrize(
    ("charge", "discharge", "expected"),
    [
        (True, False, "entladen_gesperrt"),
        (False, True, "laden_gesperrt"),
        (False, False, "gesperrt"),
        (None, None, "bereit"),  # Gerät sagt nichts → keine Sperre (Vertrag 1.2)
    ],
)
async def test_schnittstellen_sensor_zeigt_geraetesperre(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    charge: bool | None,
    discharge: bool | None,
    expected: str,
) -> None:
    _entry, entity_ids = await _setup_with_state(
        hass, monkeypatch, _state(charge_allowed=charge, discharge_allowed=discharge)
    )

    assert hass.states.get(entity_ids["hems_schnittstelle"]).state == expected


async def test_schnittstellen_sensor_getrennt_bei_pollfehler(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fällt die Geräteverbindung aus, bleibt der Sensor verfügbar und meldet `getrennt` — das
    HEMS liest daraus ungültige Messwerte und fährt den Speicher in den sicheren Zustand."""
    entry, entity_ids = await _setup_with_state(
        hass, monkeypatch, _state(charge_allowed=True, discharge_allowed=False)
    )
    monkeypatch.setattr(
        MarstekUdpAdapter, "read", AsyncMock(side_effect=StorageAdapterError("keine Antwort"))
    )
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    sensor = hass.states.get(entity_ids["hems_schnittstelle"])
    assert sensor.state == "getrennt"
    assert sensor.attributes["messung_ok"] is False
    assert sensor.attributes["soc_prozent"] is None
    assert sensor.attributes["entladen_freigegeben"] is None


async def test_schnittstellen_sensor_spiegelt_anforderung_auch_in_pause(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Spiegel zeigt den Helferstand, auch wenn die Anbindung pausiert und nichts sendet."""
    entry, entity_ids = await _setup_with_state(hass, monkeypatch, _state())
    await entry.runtime_data.hems_bridge.async_pause()

    hass.states.async_set(_POWER_ENTITY, "450")
    await hass.async_block_till_done()

    assert hass.states.get(entity_ids["hems_schnittstelle"]).attributes["hems_anforderung_w"] == 450


async def test_schnittstellen_sensor_zeichnet_fluechtige_attribute_nicht_auf() -> None:
    """Leistungen und Zeitstempel ändern sich im Sekundentakt — nicht in den Recorder."""
    from custom_components.battery_bridge.sensor import BatteryBridgeHemsInterfaceSensor

    unrecorded = BatteryBridgeHemsInterfaceSensor._unrecorded_attributes
    assert {
        "ist_ladeleistung_w",
        "ist_entladeleistung_w",
        "hems_anforderung_w",
        "gesendet_ladeleistung_w",
        "gesendet_entladeleistung_w",
        "gemessen_am",
    } <= unrecorded
    assert "entladen_freigegeben" not in unrecorded
    assert "sperrgruende" not in unrecorded
