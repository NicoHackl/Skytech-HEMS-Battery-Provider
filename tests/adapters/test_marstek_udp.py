"""Tests für den Marstek-UDP-Adapter — ohne echten Socket, ohne Netzwerkzugriff.

`create_datagram_endpoint` wird gemockt: ein `_FakeTransport` beantwortet jeden `sendto()`
synchron über eine Responder-Funktion, indem er die Antwort direkt in die Protocol-Queue legt.
Das hält die Tests deterministisch und ohne echten Port — siehe docs/test-strategie.md
(„Tests laufen ohne Netzwerkzugriff").
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import pytest

from custom_components.battery_bridge.adapters import marstek_udp
from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.marstek_udp import MarstekUdpAdapter

Responder = Callable[[dict], "dict | None"]


class _FakeTransport:
    """Ersetzt den echten `asyncio.DatagramTransport` — `sendto()` löst die Antwort direkt aus."""

    def __init__(self, protocol: asyncio.DatagramProtocol, responder: Responder) -> None:
        self._protocol = protocol
        self._responder = responder
        self.sent: list[dict] = []
        self.closed = False

    def sendto(self, data: bytes, addr: object = None) -> None:
        request = json.loads(data)
        self.sent.append(request)
        reply = self._responder(request)
        if reply is not None:
            self._protocol.datagram_received(json.dumps(reply).encode(), ("127.0.0.1", 0))

    def close(self) -> None:
        self.closed = True


async def _connected_adapter(
    monkeypatch: pytest.MonkeyPatch, responder: Responder
) -> MarstekUdpAdapter:
    """`MarstekUdpAdapter`, dessen Transport-Erzeugung auf `_FakeTransport` umgeleitet ist."""

    async def fake_create_datagram_endpoint(protocol_factory, **_kwargs):
        protocol = protocol_factory()
        transport = _FakeTransport(protocol, responder)
        return transport, protocol

    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "create_datagram_endpoint", fake_create_datagram_endpoint)

    adapter = MarstekUdpAdapter("127.0.0.1", 30000)
    await adapter.connect()
    return adapter


def _status_responder(result: dict) -> Responder:
    return lambda request: {"id": request["id"], "src": "test", "result": result}


async def test_read_liest_soc_und_ladeleistung_im_normalfall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalfall: positive bat_power (laden) landet in charge_power_w, nicht discharge."""
    adapter = await _connected_adapter(
        monkeypatch, _status_responder({"bat_soc": 55, "bat_power": 420})
    )
    state = await adapter.read()

    assert state.available is True
    assert state.soc_percent == 55
    assert state.charge_power_w == 420
    assert state.discharge_power_w == 0


async def test_read_liest_entladeleistung_bei_negativer_bat_power(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative bat_power (entladen) landet in discharge_power_w, nie in charge_power_w."""
    adapter = await _connected_adapter(
        monkeypatch, _status_responder({"bat_soc": 40, "bat_power": -730})
    )
    state = await adapter.read()

    assert state.charge_power_w == 0
    assert state.discharge_power_w == 730


async def test_read_leerzustand_bei_fehlenden_feldern(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leerzustand: fehlende Felder werden None, nie 0 oder ein geratener Wert."""
    adapter = await _connected_adapter(monkeypatch, _status_responder({}))
    state = await adapter.read()

    assert state.soc_percent is None
    assert state.charge_power_w is None
    assert state.discharge_power_w is None
    assert state.available is True  # Antwort kam an, nur ohne die erwarteten Felder


async def test_read_fehlerfall_wirft_nach_retries_storage_adapter_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fehlerfall: Gerät antwortet nie → StorageAdapterError, kein stiller Fehlschlag."""
    monkeypatch.setattr(marstek_udp, "_REQUEST_TIMEOUT_S", 0.02)
    monkeypatch.setattr(marstek_udp, "_REQUEST_RETRIES", 2)
    adapter = await _connected_adapter(monkeypatch, lambda _request: None)

    with pytest.raises(StorageAdapterError):
        await adapter.read()


async def test_read_verwirft_antwort_mit_falscher_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Antwort mit fremder id wird verworfen, nie als aktuelles Ergebnis übernommen."""
    monkeypatch.setattr(marstek_udp, "_REQUEST_TIMEOUT_S", 0.02)
    monkeypatch.setattr(marstek_udp, "_REQUEST_RETRIES", 2)

    def responder(request: dict) -> dict:
        return {"id": request["id"] + 1, "src": "test", "result": {"bat_soc": 99}}

    adapter = await _connected_adapter(monkeypatch, responder)

    with pytest.raises(StorageAdapterError):
        await adapter.read()


async def test_read_wirft_bei_fehlerantwort_ohne_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """Antwort ohne `result` (Gerätefehler) wird nicht als leerer Erfolg interpretiert."""

    def responder(request: dict) -> dict:
        return {"id": request["id"], "src": "test", "error": "unbekannte Methode"}

    adapter = await _connected_adapter(monkeypatch, responder)

    with pytest.raises(StorageAdapterError):
        await adapter.read()


async def test_read_ohne_connect_wirft_storage_adapter_error() -> None:
    """Adapter, der nie connect() sah, wirft einen sprechenden Fehler statt AttributeError."""
    adapter = MarstekUdpAdapter("127.0.0.1", 1)
    with pytest.raises(StorageAdapterError):
        await adapter.read()


def _set_mode_responder(*, accept: bool) -> tuple[Responder, list[dict]]:
    """Responder für ES.SetMode, der jeden gesendeten Request zur Prüfung mitschneidet."""
    sent: list[dict] = []

    def responder(request: dict) -> dict:
        sent.append(request)
        return {"id": request["id"], "src": "test", "result": {"id": 0, "set_result": accept}}

    return responder, sent


async def test_write_charge_power_sendet_negativen_passive_sollwert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Laden → Passive-Mode-`power` negativ, siehe Adapter-Moduldoc zur Vorzeichenkonvention."""
    responder, sent = _set_mode_responder(accept=True)
    adapter = await _connected_adapter(monkeypatch, responder)

    await adapter.write_charge_power(500)

    assert len(sent) == 1
    config = sent[0]["params"]["config"]
    assert config["mode"] == "Passive"
    assert config["passive_cfg"]["power"] == -500


async def test_write_discharge_power_sendet_positiven_passive_sollwert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entladen → Passive-Mode-`power` positiv."""
    responder, sent = _set_mode_responder(accept=True)
    adapter = await _connected_adapter(monkeypatch, responder)

    await adapter.write_discharge_power(750)

    config = sent[0]["params"]["config"]
    assert config["passive_cfg"]["power"] == 750


async def test_write_wirft_wenn_geraet_sollwert_ablehnt(monkeypatch: pytest.MonkeyPatch) -> None:
    """`set_result: false` ist ein abgelehnter Sollwert, kein stiller Erfolg."""
    responder, _sent = _set_mode_responder(accept=False)
    adapter = await _connected_adapter(monkeypatch, responder)

    with pytest.raises(StorageAdapterError):
        await adapter.write_charge_power(500)
