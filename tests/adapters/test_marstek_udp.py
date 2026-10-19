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
        self.protocol = protocol
        self._responder = responder
        self.sent: list[dict] = []
        self.closed = False

    def sendto(self, data: bytes, addr: object = None) -> None:
        request = json.loads(data)
        self.sent.append(request)
        reply = self._responder(request)
        if reply is not None:
            self.protocol.datagram_received(json.dumps(reply).encode(), ("127.0.0.1", 0))

    def close(self) -> None:
        self.closed = True

    def is_closing(self) -> bool:
        return self.closed


def _patch_endpoint(monkeypatch: pytest.MonkeyPatch, responder: Responder) -> list[_FakeTransport]:
    """Transport-Erzeugung auf `_FakeTransport` umleiten und jeden erzeugten Transport sammeln.

    Die Liste ist der Nachweis für einen Neuaufbau: ein zweiter Eintrag heißt, der Adapter hat
    sich einen frischen Socket geholt (siehe `adapters/marstek_udp.py`, Abschnitt Verbindungs-
    abbruch im Moduldoc).
    """
    transports: list[_FakeTransport] = []

    async def fake_create_datagram_endpoint(protocol_factory, **_kwargs):
        protocol = protocol_factory()
        transport = _FakeTransport(protocol, responder)
        transports.append(transport)
        return transport, protocol

    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "create_datagram_endpoint", fake_create_datagram_endpoint)
    return transports


async def _connected_adapter_with_transports(
    monkeypatch: pytest.MonkeyPatch, responder: Responder
) -> tuple[MarstekUdpAdapter, list[_FakeTransport]]:
    """Wie `_connected_adapter()`, gibt zusätzlich die Liste der erzeugten Transports zurück."""
    transports = _patch_endpoint(monkeypatch, responder)
    adapter = MarstekUdpAdapter("127.0.0.1", 30000)
    await adapter.connect()
    return adapter, transports


async def _connected_adapter(
    monkeypatch: pytest.MonkeyPatch, responder: Responder
) -> MarstekUdpAdapter:
    """`MarstekUdpAdapter`, dessen Transport-Erzeugung auf `_FakeTransport` umgeleitet ist."""
    adapter, _transports = await _connected_adapter_with_transports(monkeypatch, responder)
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


async def test_read_nutzt_ongrid_power_wenn_bat_power_fehlt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fehlt `bat_power` komplett (an echter Hardware beobachtet, siehe bekannte-luecken.md),
    wird `ongrid_power` als Ersatz herangezogen — negiert, da dort positiv „einspeisen"
    (= entladen) bedeutet, negativ „vom Netz beziehen" (= laden)."""
    adapter = await _connected_adapter(
        monkeypatch, _status_responder({"bat_soc": 85, "ongrid_power": -420, "offgrid_power": 0})
    )
    state = await adapter.read()

    assert state.charge_power_w == 420  # negatives ongrid_power → laden
    assert state.discharge_power_w == 0


async def test_read_ongrid_power_positiv_ergibt_entladeleistung(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = await _connected_adapter(
        monkeypatch, _status_responder({"bat_soc": 85, "ongrid_power": 538})
    )
    state = await adapter.read()

    assert state.charge_power_w == 0
    assert state.discharge_power_w == 538


async def test_read_ignoriert_ongrid_power_wenn_bat_power_vorhanden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`bat_power` hat Vorrang — `ongrid_power` ist nur der Notbehelf, wenn es fehlt."""
    adapter = await _connected_adapter(
        monkeypatch,
        _status_responder({"bat_soc": 85, "bat_power": 100, "ongrid_power": -9999}),
    )
    state = await adapter.read()

    assert state.charge_power_w == 100
    assert state.discharge_power_w == 0


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


async def test_gleichzeitige_aufrufe_teilen_sich_nicht_die_antwort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """read() (Coordinator) und write_*() (HEMS-Anbindung) laufen auf demselben Adapter, aber
    als unabhängige Tasks nebeneinander. Ohne Serialisierung konnte die Antwort auf Request A
    bei der wartenden Schleife von Request B landen und wurde dort mangels ID-Match verworfen
    (`continue`) statt A zugestellt zu werden — A timeoutete, obwohl das Gerät geantwortet hat.
    Dieser Test hält einen ersten Request gezielt offen und startet währenddessen einen
    zweiten: Der zweite darf sein Paket erst senden, nachdem der erste seine Antwort erhalten
    hat — sonst könnten sich beide Antworten wie beschrieben in die Quere kommen.
    """
    reply_released = asyncio.Event()
    sent: list[dict] = []

    class _DeferredTransport:
        def __init__(self, protocol: asyncio.DatagramProtocol) -> None:
            self._protocol = protocol
            self.closed = False

        def sendto(self, data: bytes, addr: object = None) -> None:
            request = json.loads(data)
            sent.append(request)

            async def _deliver() -> None:
                await reply_released.wait()
                reply = {"id": request["id"], "src": "test", "result": {"bat_soc": 1}}
                self._protocol.datagram_received(json.dumps(reply).encode(), ("127.0.0.1", 0))

            asyncio.ensure_future(_deliver())

        def close(self) -> None:
            self.closed = True

        def is_closing(self) -> bool:
            return self.closed

    async def fake_create_datagram_endpoint(protocol_factory, **_kwargs):
        protocol = protocol_factory()
        return _DeferredTransport(protocol), protocol

    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "create_datagram_endpoint", fake_create_datagram_endpoint)
    adapter = MarstekUdpAdapter("127.0.0.1", 30000)
    await adapter.connect()

    task_a = asyncio.ensure_future(adapter.read())
    await asyncio.sleep(0)  # Request A ist gesendet, wartet auf Antwort
    assert len(sent) == 1

    task_b = asyncio.ensure_future(adapter.read())
    await asyncio.sleep(0)
    # Request B darf noch nicht gesendet sein — der Lock hält B, bis A fertig ist.
    assert len(sent) == 1

    reply_released.set()
    await task_a
    await task_b
    # Je read() genau ein ES.GetStatus; dazu höchstens einmal der Gerätestatus (Bat.GetStatus,
    # D-017), der im 15-s-Takt zwischengespeichert wird und deshalb hier nur einmal anfällt.
    assert [request["method"] for request in sent].count("ES.GetStatus") == 2
    assert [request["method"] for request in sent].count("Bat.GetStatus") == 1


async def test_geschlossener_transport_wird_vor_dem_naechsten_aufruf_neu_aufgebaut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein toter Socket meldet sich nicht, er schweigt nur — `sendto()` verpufft danach still.
    Vor dem Ausfall am 10.09.2026 half dagegen ausschließlich ein Neuladen der Integration; jetzt
    erkennt der Adapter den Zustand selbst und holt sich einen frischen Socket.
    """
    adapter, transports = await _connected_adapter_with_transports(
        monkeypatch, _status_responder({"bat_soc": 42})
    )
    assert len(transports) == 1

    transports[0].close()  # asyncio hat den Transport fallen lassen
    state = await adapter.read()

    assert state.soc_percent == 42
    assert len(transports) == 2  # neuer Socket, neuer Quellport


async def test_connection_lost_erzwingt_den_neuaufbau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auch ohne `is_closing()` darf ein verlorener Transport nicht weiterbenutzt werden —
    `connection_lost()` ist das Signal, das bisher komplett fehlte."""
    adapter, transports = await _connected_adapter_with_transports(
        monkeypatch, _status_responder({"bat_soc": 7})
    )
    transports[0].protocol.connection_lost(OSError("Netzwerk weg"))

    state = await adapter.read()

    assert state.soc_percent == 7
    assert len(transports) == 2


async def test_reconnect_erst_nach_mehreren_erfolglosen_aufrufen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein einzelnes verlorenes Paket erzwingt noch keinen neuen Socket — erst
    `_RECONNECT_AFTER_FAILED_CALLS` erfolglose Aufrufe hintereinander tun das."""
    monkeypatch.setattr(marstek_udp, "_REQUEST_TIMEOUT_S", 0.02)
    monkeypatch.setattr(marstek_udp, "_REQUEST_RETRIES", 1)
    monkeypatch.setattr(marstek_udp, "_RECONNECT_AFTER_FAILED_CALLS", 2)
    adapter, transports = await _connected_adapter_with_transports(
        monkeypatch, lambda _request: None
    )

    with pytest.raises(StorageAdapterError):
        await adapter.read()
    assert len(transports) == 1  # erster Fehlschlag: Transport bleibt

    with pytest.raises(StorageAdapterError):
        await adapter.read()  # zweiter Fehlschlag verwirft ihn

    with pytest.raises(StorageAdapterError):
        await adapter.read()
    assert len(transports) == 2


async def test_erfolgreicher_aufruf_setzt_den_fehlerzaehler_zurueck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fehlschläge müssen aufeinanderfolgen. Ein zwischenzeitlicher Erfolg beweist, dass der
    Socket lebt — dann wäre ein Neuaufbau reine Unruhe."""
    monkeypatch.setattr(marstek_udp, "_REQUEST_TIMEOUT_S", 0.02)
    monkeypatch.setattr(marstek_udp, "_REQUEST_RETRIES", 1)
    monkeypatch.setattr(marstek_udp, "_RECONNECT_AFTER_FAILED_CALLS", 2)
    antwortet = {"aktiv": False}

    def responder(request: dict) -> dict | None:
        if not antwortet["aktiv"]:
            return None
        return {"id": request["id"], "src": "test", "result": {"bat_soc": 33}}

    adapter, transports = await _connected_adapter_with_transports(monkeypatch, responder)

    with pytest.raises(StorageAdapterError):
        await adapter.read()

    antwortet["aktiv"] = True
    assert (await adapter.read()).soc_percent == 33

    antwortet["aktiv"] = False
    with pytest.raises(StorageAdapterError):
        await adapter.read()

    assert len(transports) == 1


async def test_alte_antwort_gilt_nicht_als_antwort_auf_den_naechsten_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine verspätete Antwort eines früheren Requests liegt noch in der Queue. Sie darf nicht
    als Antwort auf den nächsten Aufruf durchgehen — die Queue wird vor dem Senden geleert.
    Der Request-Zähler beginnt bei 1, die alte Antwort trägt hier bewusst genau diese id."""
    monkeypatch.setattr(marstek_udp, "_REQUEST_TIMEOUT_S", 0.02)
    monkeypatch.setattr(marstek_udp, "_REQUEST_RETRIES", 1)
    adapter, transports = await _connected_adapter_with_transports(
        monkeypatch, lambda _request: None
    )
    alte_antwort = {"id": 1, "src": "test", "result": {"bat_soc": 99}}
    transports[0].protocol.datagram_received(json.dumps(alte_antwort).encode(), ("127.0.0.1", 0))

    with pytest.raises(StorageAdapterError):
        await adapter.read()


def _method_responder(results: dict[str, dict | None]) -> Responder:
    """Antwort je Methode; `None` als Ergebnis heißt: das Gerät meldet für diese Methode einen
    Fehler (Antwort ohne `result`)."""

    def responder(request: dict) -> dict:
        result = results.get(request["method"], {})
        if result is None:
            return {"id": request["id"], "src": "test", "error": "nicht unterstützt"}
        return {"id": request["id"], "src": "test", "result": result}

    return responder


async def test_read_liest_geraetefreigaben_aus_bat_getstatus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-017: charg_flag/dischrg_flag landen als Freigabe im StorageState, mit Sperrgrund."""
    adapter = await _connected_adapter(
        monkeypatch,
        _method_responder(
            {
                "ES.GetStatus": {"bat_soc": 14, "ongrid_power": 0},
                "Bat.GetStatus": {
                    "soc": 14,
                    "charg_flag": True,
                    "dischrg_flag": False,
                    "bat_temp": 21.5,
                    "rated_capacity": 5120,
                },
            }
        ),
    )
    state = await adapter.read()

    assert state.charge_allowed is True
    assert state.discharge_allowed is False
    assert state.lock_reasons == ("geraet_entladen_gesperrt",)
    assert state.temperature_c == 21.5
    assert state.rated_capacity_wh == 5120
    assert state.soc_percent == 14  # Messwerte bleiben aus ES.GetStatus


async def test_geraetestatus_wird_nur_im_status_takt_abgefragt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bat.GetStatus höchstens alle STATUS_POLL_INTERVAL — der Netzwerkteil des Marstek verträgt
    keine zusätzliche Abfrage in jedem 5-s-Poll (D-014)."""
    now = [1000.0]
    monkeypatch.setattr(marstek_udp.time, "monotonic", lambda: now[0])
    adapter, transports = await _connected_adapter_with_transports(
        monkeypatch,
        _method_responder(
            {"ES.GetStatus": {"bat_soc": 50}, "Bat.GetStatus": {"dischrg_flag": True}}
        ),
    )

    await adapter.read()
    now[0] += 5
    second = await adapter.read()
    now[0] += 11  # 16 s nach der ersten Abfrage
    await adapter.read()

    methods = [request["method"] for request in transports[0].sent]
    assert methods.count("ES.GetStatus") == 3
    assert methods.count("Bat.GetStatus") == 2
    assert second.discharge_allowed is True  # zwischengespeicherter Wert gilt weiter


async def test_fehlender_geraetestatus_laesst_freigaben_offen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Beantwortet das Gerät Bat.GetStatus nicht, bleiben die Freigaben None — der Poll selbst
    scheitert deswegen nicht (Vertrag 1.2: None = Gerät sagt nichts)."""
    adapter = await _connected_adapter(
        monkeypatch,
        _method_responder({"ES.GetStatus": {"bat_soc": 50}, "Bat.GetStatus": None}),
    )
    state = await adapter.read()

    assert state.available is True
    assert state.soc_percent == 50
    assert state.charge_allowed is None
    assert state.discharge_allowed is None
    assert state.lock_reasons == ()


async def test_nicht_boolesche_flags_werden_nicht_geraten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Liefert das Gerät 0/1 oder Text statt true/false, wird daraus keine Freigabe abgeleitet."""
    adapter = await _connected_adapter(
        monkeypatch,
        _method_responder(
            {
                "ES.GetStatus": {"bat_soc": 50},
                "Bat.GetStatus": {"charg_flag": 0, "dischrg_flag": "1"},
            }
        ),
    )
    state = await adapter.read()

    assert state.charge_allowed is None
    assert state.discharge_allowed is None


# ---------------------------------------------------------------------------
# Soll/Ist-Vergleich (D-018)
# ---------------------------------------------------------------------------


class _FakeMarstek:
    """Gerät, das Passive-Sollwerte bestätigt und SoC/Ist-Leistung frei einstellbar meldet."""

    def __init__(self) -> None:
        self.soc = 12
        self.ongrid = 0  # positiv = speist ins Netz (entladen), negativ = bezieht (laden)
        self.dischrg_flag = True

    def __call__(self, request: dict) -> dict:
        method = request["method"]
        if method == "ES.SetMode":
            result: dict = {"set_result": True}
        elif method == "Bat.GetStatus":
            result = {"charg_flag": True, "dischrg_flag": self.dischrg_flag}
        else:
            result = {"bat_soc": self.soc, "ongrid_power": self.ongrid}
        return {"id": request["id"], "src": "test", "result": result}


async def _check_adapter(monkeypatch: pytest.MonkeyPatch, fake: _FakeMarstek, **kwargs):
    now = [1000.0]
    monkeypatch.setattr(marstek_udp.time, "monotonic", lambda: now[0])
    _patch_endpoint(monkeypatch, fake)
    adapter = MarstekUdpAdapter("127.0.0.1", 30000, **kwargs)
    await adapter.connect()

    async def poll(seconds: float = 5):
        now[0] += seconds
        return await adapter.read()

    return adapter, poll


async def test_verweigerte_entladung_sperrt_nach_erkennungszeit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vorfall 19.10.2026: SoC 12 %, Sollwert bestätigt, Ist bleibt 0 W, dischrg_flag true."""
    fake = _FakeMarstek()
    adapter, poll = await _check_adapter(monkeypatch, fake)
    await adapter.write_discharge_power(528)

    state = await poll(0)
    for _ in range(5):
        state = await poll()
        assert state.discharge_allowed is True  # 25 s: noch nicht
    state = await poll()  # 30 s ohne Reaktion

    assert state.discharge_allowed is False
    assert "keine_reaktion_entladen" in state.lock_reasons
    assert state.charge_allowed is True
    assert state.lock_release_soc_percent == 13


async def test_fehlzeit_summiert_ueber_mehrere_anforderungen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pendeln wie am 18.10.2026: kurze Entladeanforderungen, dazwischen Laden."""
    fake = _FakeMarstek()
    adapter, poll = await _check_adapter(monkeypatch, fake)
    await poll(0)
    for _ in range(3):
        await adapter.write_discharge_power(1400)
        await poll()
        await poll()  # 10 s ohne Reaktion
        await adapter.write_charge_power(400)
        fake.ongrid = -400  # Laden funktioniert
        await poll()
        fake.ongrid = 0
    await adapter.write_discharge_power(1400)
    state = await poll()  # 3 × 10 s = 30 s Fehlzeit beim Entladen

    assert state.discharge_allowed is False
    assert state.charge_allowed is True


async def test_lieferung_setzt_fehlzeit_zurueck(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeMarstek()
    adapter, poll = await _check_adapter(monkeypatch, fake)
    await adapter.write_discharge_power(500)
    await poll(0)
    for _ in range(5):
        await poll()  # 25 s
    fake.ongrid = 480
    await poll()  # liefert → 0
    fake.ongrid = 0
    for _ in range(5):
        state = await poll()

    assert state.discharge_allowed is True


async def test_entladesperre_faellt_bei_soc_plus_ein_prozent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeMarstek()
    adapter, poll = await _check_adapter(monkeypatch, fake)
    await adapter.write_discharge_power(500)
    await poll(0)
    for _ in range(6):
        state = await poll()
    assert state.discharge_allowed is False

    await adapter.write_charge_power(300)  # HEMS lädt aus PV, Speicher reagiert
    fake.ongrid = -300
    state = await poll()
    assert state.discharge_allowed is False  # SoC noch 12 %
    fake.soc = 13
    state = await poll()

    assert state.discharge_allowed is True
    assert "keine_reaktion_entladen" not in state.lock_reasons
    assert state.lock_release_soc_percent is None


async def test_ladesperre_faellt_bei_soc_minus_ein_prozent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeMarstek()
    fake.soc = 60
    adapter, poll = await _check_adapter(monkeypatch, fake)
    await adapter.write_charge_power(800)
    await poll(0)
    for _ in range(6):
        state = await poll()
    assert state.charge_allowed is False
    assert "keine_reaktion_laden" in state.lock_reasons
    assert state.lock_release_soc_percent == 59

    fake.soc = 59
    state = await poll()
    assert state.charge_allowed is True


async def test_kleiner_sollwert_wird_nicht_geprueft(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeMarstek()
    adapter, poll = await _check_adapter(monkeypatch, fake)
    await adapter.write_discharge_power(80)
    await poll(0)
    for _ in range(10):
        state = await poll()

    assert state.discharge_allowed is True


async def test_erkennungszeit_null_schaltet_vergleich_ab(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeMarstek()
    adapter, poll = await _check_adapter(monkeypatch, fake, response_check_time_s=0)
    await adapter.write_discharge_power(500)
    await poll(0)
    for _ in range(20):
        state = await poll()

    assert state.discharge_allowed is True


async def test_pollluecke_zaehlt_nicht_auf_einmal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nach einer Ausfallphase zählt höchstens das Doppelte des Abfrageintervalls."""
    fake = _FakeMarstek()
    adapter, poll = await _check_adapter(monkeypatch, fake, poll_interval_s=5)
    await adapter.write_discharge_power(500)
    await poll(0)
    state = await poll(300)

    assert state.discharge_allowed is True


async def test_geraeteflag_und_vergleich_wirken_gemeinsam(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeMarstek()
    fake.dischrg_flag = False
    adapter, poll = await _check_adapter(monkeypatch, fake)
    state = await poll(0)

    assert state.discharge_allowed is False
    assert state.lock_reasons == ("geraet_entladen_gesperrt",)
