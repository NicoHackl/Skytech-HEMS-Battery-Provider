"""Tests für die optionale, eingebaute HEMS-Anbindung (hems_bridge.py, D-009)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter
from custom_components.battery_bridge.models import StorageState
from tests.conftest import make_marstek_entry

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_PREFIX = "acspeicher1"
_POWER_ENTITY = f"input_number.ems_{_PREFIX}_anforderung_leistung_w"
_MODE_ENTITY = f"input_select.ems_{_PREFIX}_anforderung_betriebsart"


async def _setup_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    *,
    hems_entity_prefix: str | None = _PREFIX,
) -> tuple[list[tuple[str, float]], object]:
    """Entry einrichten, alle Adapter-Schreibaufrufe in Reihenfolge aufzeichnen."""
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

    return calls, entry


async def _set_anforderung(hass: HomeAssistant, *, leistung_w: str, betriebsart: str) -> None:
    """HEMS-Anforderung setzen — Leistung zuerst (Betriebsart fehlt dann noch, kein Sync),
    Betriebsart danach (jetzt sind beide Helfer vorhanden, genau ein sauberer Sync)."""
    hass.states.async_set(_POWER_ENTITY, leistung_w)
    await hass.async_block_till_done()
    hass.states.async_set(_MODE_ENTITY, betriebsart)
    await hass.async_block_till_done()


async def test_laden_setzt_erst_entladeleistung_auf_null_dann_ladeleistung(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kein additives Zwei-Kanal-Signal am Gerät: inaktive Richtung zuerst auf 0, danach erst
    die aktive Richtung — sonst könnte je nach Aufrufreihenfolge die falsche Richtung gewinnen."""
    calls, _entry = await _setup_entry(hass, monkeypatch)

    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")

    assert calls == [("discharge", 0.0), ("charge", 800.0)]


async def test_entladen_setzt_erst_ladeleistung_auf_null_dann_entladeleistung(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls, _entry = await _setup_entry(hass, monkeypatch)

    await _set_anforderung(hass, leistung_w="-500", betriebsart="entladen")

    assert calls == [("charge", 0.0), ("discharge", 500.0)]


async def test_standby_setzt_beide_richtungen_auf_null(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls, _entry = await _setup_entry(hass, monkeypatch)

    await _set_anforderung(hass, leistung_w="0", betriebsart="standby")

    assert calls == [("charge", 0.0), ("discharge", 0.0)]


async def test_unerwartete_betriebsart_wird_wie_standby_behandelt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nicht raten, was ein unbekannter/leerer Wert bedeuten soll — sicherer Fall statt Absturz."""
    calls, _entry = await _setup_entry(hass, monkeypatch)

    await _set_anforderung(hass, leistung_w="300", betriebsart="unknown")

    assert calls == [("charge", 0.0), ("discharge", 0.0)]


async def test_nicht_numerische_leistung_wird_als_null_behandelt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls, _entry = await _setup_entry(hass, monkeypatch)

    await _set_anforderung(hass, leistung_w="unavailable", betriebsart="laden")

    assert calls == [("discharge", 0.0), ("charge", 0.0)]


async def test_gleichbleibende_betriebsart_setzt_inaktive_richtung_nicht_erneut_auf_null(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bleibt die Betriebsart gleich, darf eine reine Leistungsanpassung die inaktive Richtung
    nicht erneut auf 0 setzen — sonst träfen zwei Befehle (0, dann Zielwert) hintereinander
    denselben Passive-Mode-Sollwert und der Speicher spränge bei jeder Anpassung kurz auf 0 W."""
    calls, _entry = await _setup_entry(hass, monkeypatch)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    calls.clear()

    hass.states.async_set(_POWER_ENTITY, "950")  # nur die Leistung ändert sich
    await hass.async_block_till_done()

    assert calls == [("charge", 950.0)]  # kein ("discharge", 0.0) davor


async def test_wechsel_der_betriebsart_setzt_inaktive_richtung_erneut_auf_null(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein tatsächlicher Richtungswechsel muss die bisher aktive Richtung weiterhin auf 0
    setzen, bevor die neue Richtung greift."""
    calls, _entry = await _setup_entry(hass, monkeypatch)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    calls.clear()

    hass.states.async_set(_MODE_ENTITY, "entladen")
    await hass.async_block_till_done()

    assert calls == [("charge", 0.0), ("discharge", 800.0)]


async def test_nach_fehlgeschlagenem_wechsel_wird_beim_naechsten_sync_erneut_genullt(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Schlägt der Zero-Schritt bei einem Richtungswechsel fehl, gilt der Wechsel nicht als
    übernommen — der nächste Sync muss ihn erneut versuchen, statt dauerhaft von der falschen,
    zuvor aktiven Richtung auszugehen."""
    calls, _entry = await _setup_entry(hass, monkeypatch)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    calls.clear()

    monkeypatch.setattr(
        MarstekUdpAdapter,
        "write_charge_power",
        AsyncMock(side_effect=StorageAdapterError("boom")),
    )
    hass.states.async_set(_MODE_ENTITY, "entladen")
    await hass.async_block_till_done()
    assert calls == []  # write_charge_power(0) ist der erste Aufruf und schlägt sofort fehl

    monkeypatch.setattr(
        MarstekUdpAdapter,
        "write_charge_power",
        AsyncMock(side_effect=lambda watts: calls.append(("charge", watts))),
    )
    hass.states.async_set(_POWER_ENTITY, "801")  # neuer Wert löst einen neuen Sync aus
    await hass.async_block_till_done()

    assert calls == [("charge", 0.0), ("discharge", 801.0)]


async def test_schreibfehler_wird_geloggt_nicht_propagiert(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ein Fehlschlag beim Schreiben darf den Listener nicht lahmlegen (kein Crash im Event-Bus,
    kein stiller Fehlschlag — die technische Ursache steht im Log)."""
    calls, _entry = await _setup_entry(hass, monkeypatch)
    technical_detail = "Marstek 127.0.0.1:30000 antwortet nach 3 Versuchen nicht auf ES.SetMode."
    monkeypatch.setattr(
        MarstekUdpAdapter,
        "write_charge_power",
        AsyncMock(side_effect=StorageAdapterError(technical_detail)),
    )

    with caplog.at_level(logging.ERROR):
        await _set_anforderung(hass, leistung_w="800", betriebsart="laden")

    assert calls == [("discharge", 0.0)]  # inaktive Richtung lief noch durch, dann der Fehler
    assert technical_detail in caplog.text


async def test_ohne_hems_praefix_bleibt_die_integration_reiner_entity_lieferant(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kein HEMS-Präfix konfiguriert → kein Listener, HEMS-Helfer-Änderungen bleiben wirkungslos."""
    calls, _entry = await _setup_entry(hass, monkeypatch, hems_entity_prefix=None)

    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")

    assert calls == []


async def test_unload_entfernt_den_listener(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls, entry = await _setup_entry(hass, monkeypatch)
    await _set_anforderung(hass, leistung_w="800", betriebsart="laden")
    assert calls  # HEMS-Anbindung war aktiv

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    calls.clear()

    hass.states.async_set(_MODE_ENTITY, "entladen")
    await hass.async_block_till_done()

    assert calls == []
