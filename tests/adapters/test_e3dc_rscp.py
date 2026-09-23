"""Tests für den E3DC-RSCP-Adapter (D-015) — pye3dc wird durch ein Fake-Objekt ersetzt."""

from __future__ import annotations

from typing import Any

import pytest
from e3dc import AuthenticationError, RSCPKeyError, SendError

from custom_components.battery_bridge.adapters import e3dc_rscp
from custom_components.battery_bridge.adapters.base import (
    StorageAdapterAuthError,
    StorageAdapterError,
)
from custom_components.battery_bridge.adapters.e3dc_rscp import E3dcRscpAdapter
from custom_components.battery_bridge.const import E3DC_KEEPALIVE_INTERVAL


class _FakeE3DC:
    """Steht für `e3dc.E3DC` — zeichnet gesendete Requests auf, liefert feste Poll-Werte."""

    CONNECT_LOCAL = 1

    def __init__(self, connect_type: int, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.serialNumber = "123456"
        self.serialNumberPrefix = "S10-"
        self.maxBatChargePower = 6000
        self.maxBatDischargePower = 12120
        self.requests: list[Any] = []
        self.poll_result: dict[str, Any] = {
            "stateOfCharge": 92,
            "consumption": {"battery": -243, "house": 242, "wallbox": 0},
        }
        self.poll_error: Exception | None = None
        self.send_error: Exception | None = None
        self.disconnected = False

    def poll(self, keepAlive: bool = False) -> dict[str, Any]:
        if self.poll_error is not None:
            raise self.poll_error
        return self.poll_result

    def sendRequest(self, request: Any, retries: int = 3, keepAlive: bool = False) -> Any:
        if self.send_error is not None:
            raise self.send_error
        self.requests.append(request)
        return ("EMS_SET_POWER", "Int32", request[2][1][2])

    def disconnect(self) -> None:
        self.disconnected = True


@pytest.fixture
def fake_e3dc(monkeypatch: pytest.MonkeyPatch) -> list[_FakeE3DC]:
    """Ersetzt `E3DC` im Adapter-Modul, liefert alle erzeugten Fake-Instanzen."""
    instances: list[_FakeE3DC] = []

    def factory(connect_type: int, **kwargs: Any) -> _FakeE3DC:
        instance = _FakeE3DC(connect_type, **kwargs)
        instances.append(instance)
        return instance

    factory.CONNECT_LOCAL = _FakeE3DC.CONNECT_LOCAL  # type: ignore[attr-defined]
    monkeypatch.setattr(e3dc_rscp, "E3DC", factory)
    return instances


async def _connected_adapter() -> E3dcRscpAdapter:
    adapter = E3dcRscpAdapter("10.0.0.5", 5033, "benutzer", "geheim", "schluessel")
    await adapter.connect()
    return adapter


def _sent_mode_and_value(request: Any) -> tuple[int, int]:
    assert request[0] == "EMS_REQ_SET_POWER"
    (_, _, mode), (_, _, value) = request[2]
    return mode, value


async def test_connect_uebergibt_zugangsdaten_an_pye3dc(fake_e3dc: list[_FakeE3DC]) -> None:
    """Lokale RSCP-Verbindung mit allen Zugangsdaten aus dem Config-Entry."""
    await _connected_adapter()

    assert fake_e3dc[0].kwargs == {
        "username": "benutzer",
        "password": "geheim",
        "ipAddress": "10.0.0.5",
        "key": "schluessel",
        "port": 5033,
    }


async def test_seriennummer_und_obergrenze_kommen_vom_geraet(
    fake_e3dc: list[_FakeE3DC],
) -> None:
    """unique_id aus der Seriennummer, Obergrenze = größere der gemeldeten Grenzen."""
    adapter = await _connected_adapter()

    assert adapter.serial_number == "S10-123456"
    assert adapter.max_power_w == 12120


async def test_keepalive_intervall_ist_fuenf_sekunden() -> None:
    """E3DC übernimmt nach ~10 s selbst — der Sollwert muss alle 5 s erneut kommen."""
    assert E3dcRscpAdapter.keepalive_interval == E3DC_KEEPALIVE_INTERVAL
    assert E3DC_KEEPALIVE_INTERVAL.total_seconds() == 5


async def test_read_teilt_entladen_auf(fake_e3dc: list[_FakeE3DC]) -> None:
    """Negative Batterieleistung = Entladen, SoC unverändert übernommen."""
    adapter = await _connected_adapter()

    state = await adapter.read()

    assert state.soc_percent == 92
    assert state.charge_power_w == 0
    assert state.discharge_power_w == 243
    assert state.available is True


async def test_read_teilt_laden_auf(fake_e3dc: list[_FakeE3DC]) -> None:
    """Positive Batterieleistung = Laden."""
    adapter = await _connected_adapter()
    fake_e3dc[0].poll_result = {"stateOfCharge": 40, "consumption": {"battery": 1500}}

    state = await adapter.read()

    assert state.charge_power_w == 1500
    assert state.discharge_power_w == 0


async def test_read_ohne_werte_liefert_none_statt_null(fake_e3dc: list[_FakeE3DC]) -> None:
    """Fehlende Werte bleiben `None` — nie eine geratene 0."""
    adapter = await _connected_adapter()
    fake_e3dc[0].poll_result = {}

    state = await adapter.read()

    assert state.soc_percent is None
    assert state.charge_power_w is None
    assert state.discharge_power_w is None


@pytest.mark.parametrize(
    ("method", "watts", "expected"),
    [
        ("write_charge_power", 1500, (4, 1500)),
        ("write_discharge_power", 800, (2, 800)),
        ("write_charge_power", 0, (1, 0)),
        ("write_discharge_power", 0, (1, 0)),
    ],
)
async def test_sollwert_wird_auf_betriebsart_abgebildet(
    fake_e3dc: list[_FakeE3DC], method: str, watts: float, expected: tuple[int, int]
) -> None:
    """Laden → Netzladen (4), Entladen → Entladen (2), 0 W → Leerlauf (1)."""
    adapter = await _connected_adapter()

    await getattr(adapter, method)(watts)

    assert [_sent_mode_and_value(r) for r in fake_e3dc[0].requests] == [expected]


async def test_sendefehler_wird_zu_storage_adapter_error(fake_e3dc: list[_FakeE3DC]) -> None:
    """Jeder pye3dc-Fehler kommt einheitlich als `StorageAdapterError` an."""
    adapter = await _connected_adapter()
    fake_e3dc[0].send_error = SendError("Max retries reached")

    with pytest.raises(StorageAdapterError):
        await adapter.write_charge_power(1000)


async def test_unerwartete_antwort_beim_poll_wird_zu_storage_adapter_error(
    fake_e3dc: list[_FakeE3DC],
) -> None:
    """Auch Fehler außerhalb der pye3dc-eigenen Typen werden übersetzt, nie durchgereicht."""
    adapter = await _connected_adapter()
    fake_e3dc[0].poll_error = TypeError("unerwartete Antwort")

    with pytest.raises(StorageAdapterError):
        await adapter.read()


@pytest.mark.parametrize("error", [AuthenticationError(), RSCPKeyError()])
async def test_abgelehnte_zugangsdaten_werden_zu_auth_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """Falsches Passwort oder falscher RSCP-Schlüssel → eigene Fehlerklasse für den Config-Flow."""

    def factory(connect_type: int, **kwargs: Any) -> Any:
        raise error

    factory.CONNECT_LOCAL = 1  # type: ignore[attr-defined]
    monkeypatch.setattr(e3dc_rscp, "E3DC", factory)
    adapter = E3dcRscpAdapter("10.0.0.5", 5033, "benutzer", "falsch", "schluessel")

    with pytest.raises(StorageAdapterAuthError):
        await adapter.connect()


async def test_aufruf_ohne_connect_meldet_fehler() -> None:
    """Ohne `connect()` kein stiller Aufbau, sondern ein sprechender Fehler."""
    adapter = E3dcRscpAdapter("10.0.0.5", 5033, "benutzer", "geheim", "schluessel")

    with pytest.raises(StorageAdapterError):
        await adapter.read()


async def test_close_trennt_die_sitzung(fake_e3dc: list[_FakeE3DC]) -> None:
    """`close()` trennt die RSCP-Sitzung und verwirft den Client."""
    adapter = await _connected_adapter()

    await adapter.close()

    assert fake_e3dc[0].disconnected is True
    with pytest.raises(StorageAdapterError):
        await adapter.read()
