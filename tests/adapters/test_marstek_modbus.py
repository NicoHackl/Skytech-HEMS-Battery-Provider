"""Tests für den Marstek-Modbus-Adapter — ohne echten Socket, ohne Netzwerkzugriff.

`asyncio.open_connection` wird gemockt: `_FakeDevice` beantwortet jede geschriebene Anfrage über
einen echten `asyncio.StreamReader`, so läuft das Lesen der Rahmen wie im Betrieb.
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable

import pytest

from custom_components.battery_bridge.adapters import marstek_modbus
from custom_components.battery_bridge.adapters.base import StorageAdapterError
from custom_components.battery_bridge.adapters.marstek_modbus import MarstekModbusAdapter
from custom_components.battery_bridge.const import MARSTEK_FAILED_UPDATE_INTERVAL

_SOC = 34002
_AC = 30006
_CONTROL = 42000
_FORCE = 42010
_CHARGE = 42020
_DISCHARGE = 42021


class _FakeDevice:
    """Register, Mitschnitt und steuerbares Fehlverhalten des Geräts."""

    def __init__(self) -> None:
        self.registers = {_SOC: 555, _AC: 0, _CONTROL: 21947, _FORCE: 0, _CHARGE: 0, _DISCHARGE: 0}
        self.writes: list[tuple[int, int]] = []
        self.silent = False
        self.connections = 0
        self.refuse_connection = False
        self.on_request: Callable[[int, int], bytes | None] | None = None

    def answer(self, frame: bytes) -> bytes | None:
        transaction, _protocol, _length, unit, function, register, word = struct.unpack(
            ">HHHBBHH", frame
        )
        if self.on_request is not None:
            custom = self.on_request(transaction, register)
            if custom is not None:
                return custom
        if self.silent:
            return None
        if function == 6:
            self.writes.append((register, word))
            self.registers[register] = word
            pdu = struct.pack(">BHH", 6, register, word)
        else:
            pdu = struct.pack(">BBH", 3, 2, self.registers[register] & 0xFFFF)
        return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, unit) + pdu


class _FakeWriter:
    def __init__(self, device: _FakeDevice, reader: asyncio.StreamReader) -> None:
        self._device = device
        self._reader = reader
        self.closed = False

    def write(self, data: bytes) -> None:
        reply = self._device.answer(data)
        if reply:
            self._reader.feed_data(reply)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def is_closing(self) -> bool:
        return self.closed


@pytest.fixture
def device(monkeypatch: pytest.MonkeyPatch) -> _FakeDevice:
    fake = _FakeDevice()

    async def fake_open_connection(_host: str, _port: int):
        if fake.refuse_connection:
            raise ConnectionRefusedError("refused")
        fake.connections += 1
        reader = asyncio.StreamReader()
        return reader, _FakeWriter(fake, reader)

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    monkeypatch.setattr(marstek_modbus, "_REQUEST_TIMEOUT_S", 0.02)
    monkeypatch.setattr(marstek_modbus, "_MESSAGE_WAIT_S", 0.0)
    monkeypatch.setattr(marstek_modbus, "_RECONNECT_SETTLE_S", 0.0)
    return fake


async def _adapter() -> MarstekModbusAdapter:
    adapter = MarstekModbusAdapter("127.0.0.1", 502)
    await adapter.connect()
    return adapter


def test_wartezeit_ueberbrueckt_den_telemetrie_upload() -> None:
    assert marstek_modbus._REQUEST_TIMEOUT_S * marstek_modbus._REQUEST_ATTEMPTS > 8


def test_marstek_taktet_wie_ueber_udp() -> None:
    assert MarstekModbusAdapter.failed_poll_interval == MARSTEK_FAILED_UPDATE_INTERVAL
    assert MarstekModbusAdapter.response_check_supported is True
    assert MarstekModbusAdapter.max_power_w == 2500


async def test_read_liest_soc_und_ladeleistung(device: _FakeDevice) -> None:
    """Negative AC-Leistung heißt laden, positive entladen (D-022)."""
    device.registers[_AC] = 0x10000 - 2492
    state = await (await _adapter()).read()

    assert state.soc_percent == 55.5
    assert state.charge_power_w == 2492
    assert state.discharge_power_w == 0
    assert state.available is True


async def test_read_liest_entladeleistung(device: _FakeDevice) -> None:
    device.registers[_AC] = 547
    state = await (await _adapter()).read()

    assert state.charge_power_w == 0
    assert state.discharge_power_w == 547


async def test_lesen_schaltet_die_freigabe_nicht_ein(device: _FakeDevice) -> None:
    """Der Verbindungstest im Config-Flow darf das Gerät nicht aus seinem App-Modus nehmen."""
    adapter = await _adapter()
    await adapter.read()
    await adapter.close()

    assert device.writes == []


async def test_laden_schaltet_freigabe_ein_und_setzt_leistung_vor_modus(
    device: _FakeDevice,
) -> None:
    await (await _adapter()).write_charge_power(800)

    assert device.writes == [(_CONTROL, 21930), (_CHARGE, 800), (_FORCE, 1)]


async def test_entladen_setzt_leistung_vor_modus(device: _FakeDevice) -> None:
    await (await _adapter()).write_discharge_power(750)

    assert device.writes == [(_CONTROL, 21930), (_DISCHARGE, 750), (_FORCE, 2)]


async def test_null_watt_setzt_standby_und_belaesst_die_freigabe(device: _FakeDevice) -> None:
    adapter = await _adapter()
    await adapter.write_discharge_power(750)
    device.writes.clear()

    await adapter.write_charge_power(0)
    await adapter.write_discharge_power(0)

    assert device.writes == [(_FORCE, 0)]


async def test_unveraenderter_sollwert_wird_nicht_erneut_geschrieben(device: _FakeDevice) -> None:
    adapter = await _adapter()
    await adapter.write_charge_power(800)
    device.writes.clear()

    await adapter.write_charge_power(800)
    assert device.writes == []

    await adapter.write_charge_power(900)
    assert device.writes == [(_CHARGE, 900)]


async def test_keepalive_schreibt_nach_ablauf_erneut(
    device: _FakeDevice, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(marstek_modbus, "_REWRITE_AFTER_S", 0.0)
    adapter = await _adapter()
    await adapter.write_charge_power(800)
    device.writes.clear()

    await adapter.write_charge_power(800)

    assert device.writes == [(_CHARGE, 800), (_FORCE, 1)]


async def test_sollwert_wird_auf_die_geraetegrenze_begrenzt(device: _FakeDevice) -> None:
    await (await _adapter()).write_discharge_power(9000)

    assert (_DISCHARGE, 2500) in device.writes


async def test_verlorene_freigabe_wird_gemeldet_und_beim_naechsten_sollwert_gesetzt(
    device: _FakeDevice, caplog: pytest.LogCaptureFixture
) -> None:
    """Das Gerät bestätigt Befehle dann weiter, führt sie aber nicht aus (Moduldoc)."""
    adapter = await _adapter()
    await adapter.write_charge_power(800)
    device.registers[_CONTROL] = 21947
    device.writes.clear()

    state = await adapter.read()
    await adapter.read()

    assert state.communication_interrupted is True
    assert caplog.text.count("Freigabe verloren") == 1

    await adapter.write_charge_power(800)
    assert device.writes == [(_CONTROL, 21930), (_CHARGE, 800), (_FORCE, 1)]


async def test_abweichender_modus_erneuert_den_sollwert(device: _FakeDevice) -> None:
    adapter = await _adapter()
    await adapter.write_charge_power(800)
    device.registers[_FORCE] = 0

    assert (await adapter.read()).communication_interrupted is True


async def test_normaler_poll_meldet_keinen_aussetzer(device: _FakeDevice) -> None:
    adapter = await _adapter()
    await adapter.write_charge_power(800)

    assert (await adapter.read()).communication_interrupted is False


async def test_poll_waehrend_des_schreibens_sieht_keinen_halben_sollwert(
    device: _FakeDevice,
) -> None:
    """Ein Modus, der gerade erst geschrieben wird, darf nicht als Abweichung gelten."""
    adapter = await _adapter()
    await adapter.write_charge_power(800)
    await adapter.read()

    _, state = await asyncio.gather(adapter.write_discharge_power(500), adapter.read())

    assert state.communication_interrupted is False


async def test_kurzer_aussetzer_bleibt_ohne_fehler_auf_neuer_verbindung(
    device: _FakeDevice,
) -> None:
    """Der zweite Versuch läuft auf neuer Verbindung, der Sollwert gilt danach als ungesichert."""
    adapter = await _adapter()
    await adapter.write_charge_power(800)
    await adapter.read()
    device.writes.clear()
    aussetzer = {"offen": True}

    def einmal_still(_transaction: int, _register: int) -> bytes | None:
        if aussetzer["offen"]:
            aussetzer["offen"] = False
            return b""
        return None

    device.on_request = einmal_still
    state = await adapter.read()

    assert state.communication_interrupted is True
    assert device.connections == 2
    assert (await adapter.read()).communication_interrupted is False

    await adapter.write_charge_power(800)
    assert device.writes == [(_CHARGE, 800), (_FORCE, 1)]


async def test_im_laufenden_aussetzer_nur_ein_versuch(device: _FakeDevice) -> None:
    adapter = await _adapter()
    device.silent = True

    with pytest.raises(StorageAdapterError, match="2 Versuchen"):
        await adapter.read()
    with pytest.raises(StorageAdapterError, match="einem Versuch"):
        await adapter.read()


async def test_erste_antwort_beendet_den_aussetzer(
    device: _FakeDevice, caplog: pytest.LogCaptureFixture
) -> None:
    adapter = await _adapter()
    device.silent = True
    with pytest.raises(StorageAdapterError):
        await adapter.read()

    device.silent = False
    with caplog.at_level("INFO", logger=marstek_modbus.__name__):
        state = await adapter.read()

    assert state.communication_interrupted is True
    assert "Aussetzer wieder" in caplog.text


async def test_verspaetete_antwort_wird_verworfen(device: _FakeDevice) -> None:
    """Sie gehört zu einem früheren Versuch und darf nicht als aktuelle Antwort durchgehen."""
    adapter = await _adapter()

    def erst_alte_antwort(transaction: int, register: int) -> bytes | None:
        device.on_request = None
        alt = struct.pack(">HHHBBBH", (transaction - 1) & 0xFFFF, 0, 5, 1, 3, 2, 999)
        echt = struct.pack(">HHHBBBH", transaction, 0, 5, 1, 3, 2, 321)
        return alt + echt

    device.on_request = erst_alte_antwort
    state = await adapter.read()

    assert state.soc_percent == 32.1


async def test_fehlerantwort_mit_falscher_laenge_bleibt_im_takt(device: _FakeDevice) -> None:
    """Die Firmware trägt im Kopf eine Länge zu viel ein: 9 Byte, Kopf sagt 10 (Moduldoc)."""
    adapter = await _adapter()

    def abgelehnt(transaction: int, register: int) -> bytes | None:
        device.on_request = None
        ablehnung = struct.pack(">HHHBBB", transaction, 0, 4, 1, 0x83, 2)
        return ablehnung

    device.on_request = abgelehnt
    with pytest.raises(StorageAdapterError, match="lehnt Register"):
        await adapter.read()

    assert device.connections == 1
    assert (await adapter.read()).soc_percent == 55.5


async def test_unbestaetigtes_schreiben_ist_ein_fehler(device: _FakeDevice) -> None:
    adapter = await _adapter()

    def falsches_echo(transaction: int, register: int) -> bytes | None:
        pdu = struct.pack(">BHH", 6, register, 1)
        return struct.pack(">HHHB", transaction, 0, len(pdu) + 1, 1) + pdu

    device.on_request = falsches_echo
    with pytest.raises(StorageAdapterError, match="nicht bestätigt"):
        await adapter.write_discharge_power(500)


async def test_verbindungsfehler_beim_start(device: _FakeDevice) -> None:
    device.refuse_connection = True

    with pytest.raises(StorageAdapterError, match="nicht erreichbar"):
        await _adapter()


async def test_nach_verbindungsfehler_wird_der_naechste_versuch_zurueckgehalten(
    device: _FakeDevice,
) -> None:
    """Ein Gerät im Reset nicht mit Verbindungsversuchen überhäufen (Moduldoc)."""
    adapter = await _adapter()
    device.silent = True
    device.refuse_connection = True
    with pytest.raises(StorageAdapterError):
        await adapter.read()

    device.silent = False
    device.refuse_connection = False
    verbindungen = device.connections
    with pytest.raises(StorageAdapterError):
        await adapter.read()

    assert device.connections == verbindungen


async def test_ohne_connect_wirft_der_aufruf(device: _FakeDevice) -> None:
    with pytest.raises(StorageAdapterError, match="nicht verbunden"):
        await MarstekModbusAdapter("127.0.0.1", 502).read()


async def test_close_setzt_nach_steuerung_standby_und_laesst_die_freigabe_an(
    device: _FakeDevice,
) -> None:
    """Am 05.11.2026 gemessen: das Gerät stoppt einen Force-Modus nicht von selbst."""
    adapter = await _adapter()
    await adapter.write_discharge_power(500)
    device.writes.clear()

    await adapter.close()

    assert device.writes == [(_FORCE, 0)]
    assert device.registers[_CONTROL] == 21930


async def test_close_haengt_nicht_an_einem_schweigenden_geraet(device: _FakeDevice) -> None:
    adapter = await _adapter()
    await adapter.write_discharge_power(500)
    device.silent = True

    await adapter.close()

    with pytest.raises(StorageAdapterError, match="nicht verbunden"):
        await adapter.read()


async def test_transaktions_id_laeuft_im_16_bit_bereich(device: _FakeDevice) -> None:
    adapter = await _adapter()
    adapter._transaction_id = 0xFFFF

    assert (await adapter.read()).soc_percent == 55.5
