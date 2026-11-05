"""Marstek Venus E 3.0 über Modbus TCP — zweiter Marstek-Adapter neben der UDP-API (D-022).

Warum es ihn gibt: Seit Firmware V150 setzte die UDP-API mehrfach pro Stunde 30–47 s aus, teils mit
Rampe auf rund 500 W und unangeforderter Abgabe (D-021). Am 05.11.2026 lief dasselbe Gerät über
Modbus TCP ohne diese Ereignisse.

Quelle der Register und des Zeitverhaltens ist die MIT-lizenzierte Marstek Modbus Suite
(https://github.com/sphings79/marstek-modbus-suite, `registers/e_v3.yaml`, `FIRMWARE-DROPOUTS.md`).
Von dort stammt kein Code: der Client hier ist bewusst klein und ohne weitere Abhängigkeit. Er
schickt immer nur eine Anfrage zugleich und wartet ihre Antwort ab. Ein Lesen oder Schreiben läuft
als Ganzes unter einer Sperre, damit ein Poll nie einen halb geschriebenen Sollwert sieht.

Was am Gerät zu beachten ist:

- **Freigabe (42000):** Sollwerte wirken nur, solange 42000 auf `21930` steht. Das Einschalten nimmt
  das Gerät aus seinem App-Modus. Deshalb schaltet nur ein Schreibaufruf sie ein, ein reines Lesen
  (etwa der Verbindungstest im Config-Flow) ändert am Gerät nichts. Das Gerät kann sie von selbst
  verlieren und bestätigt Befehle dann weiter, ohne sie auszuführen. Darum wird sie bei jedem Poll
  mitgelesen.
- **Kein Watchdog:** Am 05.11.2026 gemessen (V150): 100 W Entladen liefen ohne Schreibbefehl über
  3:20 min unverändert weiter. Anders als der UDP-Sollwert läuft hier nichts von selbst ab. Beim
  Entladen des Eintrags und beim HA-Stopp geht das Gerät deshalb auf Standby (`close()`). Fällt HA
  aus, ohne das zu können, hält das Gerät den letzten Sollwert (docs/bekannte-luecken.md).
- **Aussetzer:** Laut Suite blockiert der Telemetrie-Upload das Gerät rund 4 s, und der Netzwerkchip
  wird regelmäßig zurückgesetzt (bei uns alle rund 35 min). Das lässt sich hier nicht verhindern,
  nur überbrücken: 6 s Timeout, danach ein zweiter Versuch auf neuer Verbindung. Danach meldet
  `StorageState.communication_interrupted` den Aussetzer, und die HEMS-Anbindung erneuert den
  Sollwert (D-021).
- **Fehlerhafte Rahmen:** Eine Modbus-Fehlerantwort ist immer 9 Byte lang, die Firmware trägt im
  Kopf aber eine zu große Länge ein. Der Rahmen wird deshalb nicht nach dem Kopf bemessen.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from ..const import HEMS_KEEPALIVE_INTERVAL, MARSTEK_FAILED_UPDATE_INTERVAL
from ..models import StorageState
from .base import StorageAdapterError

_LOGGER = logging.getLogger(__name__)

# Register der Venus E 3.0, siehe Moduldoc.
_REG_AC_POWER: Final = 30006  # int16, W: negativ = laden, positiv = entladen (siehe D-022)
_REG_SOC: Final = 34002  # uint16, 0,1 %
_REG_CONTROL_MODE: Final = 42000
_REG_FORCE_MODE: Final = 42010
_REG_CHARGE_POWER: Final = 42020
_REG_DISCHARGE_POWER: Final = 42021

_CONTROL_MODE_ON: Final = 21930
_FORCE_STANDBY: Final = 0
_FORCE_CHARGE: Final = 1
_FORCE_DISCHARGE: Final = 2
_MAX_POWER_W: Final = 2500

_FC_READ_HOLDING: Final = 3
_FC_WRITE_SINGLE: Final = 6
_EXCEPTION_BIT: Final = 0x80
_MBAP_SIZE: Final = 7
_MAX_MBAP_LENGTH: Final = 254
_UNIT_ID: Final = 1
_MAX_TRANSACTION_ID: Final = 0xFFFF

# Zeitverhalten wie die Suite: unter rund 8 s Gesamtwartezeit entstehen schon durch den
# Telemetrie-Upload Fehler, zwei Versuche à 6 s decken ihn und einen Chip-Reset ab.
_REQUEST_TIMEOUT_S: Final = 6.0
_REQUEST_ATTEMPTS: Final = 2
_MESSAGE_WAIT_S: Final = 0.08
_RECONNECT_SETTLE_S: Final = 0.3
_CONNECT_BACKOFF_BASE_S: Final = 1.0
_CONNECT_BACKOFF_MAX_S: Final = 30.0
# Ab hier gilt eine Antwort als langsam und landet im Info-Log.
_SLOW_REPLY_S: Final = 2.0
# Unveränderte Sollwerte werden nur so oft erneut geschrieben: die HEMS-Anbindung ruft alle 60 s
# (Keep-Alive) und bei jeder Helferänderung. Knapp unter 60 s, damit der Keep-Alive auch schreibt.
_REWRITE_AFTER_S: Final = 55.0


class _DeviceRefused(StorageAdapterError):
    """Das Gerät hat mit einer Modbus-Fehlerantwort geantwortet — die Verbindung ist intakt."""


@dataclass(frozen=True, slots=True)
class _Reply:
    function: int
    payload: bytes


class MarstekModbusAdapter:
    """`StorageAdapter`-Implementierung für die Venus E 3.0 über Modbus TCP."""

    keepalive_interval = HEMS_KEEPALIVE_INTERVAL
    failed_poll_interval = MARSTEK_FAILED_UPDATE_INTERVAL
    max_power_w = _MAX_POWER_W
    # Wie über UDP meldet das Gerät eine Entladesperre nicht selbst (D-018).
    response_check_supported = True

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._transaction_id = 0
        self._last_request_finished: float | None = None
        self._last_closed: float | None = None
        self._connect_failures = 0
        self._connect_not_before = 0.0
        # Laufender Aussetzer (Uhr der Event-Loop), `None` = das Gerät antwortet (D-021).
        self._silent_since: float | None = None
        self._communication_interrupted = False
        # Was dieser Adapter am Gerät erwartet. `None` = noch nichts geschrieben: dann bleibt das
        # Gerät beim Entladen des Eintrags unangetastet (Verbindungstest im Config-Flow).
        self._desired_force: int | None = None
        self._control_mode_on: bool | None = None
        self._control_loss_logged = False
        # Register → (Wert, Zeitpunkt des letzten bestätigten Schreibens).
        self._written: dict[int, tuple[int, float]] = {}

    async def connect(self) -> None:
        self._connected = True
        async with self._lock:
            try:
                await self._ensure_open()
            except StorageAdapterError:
                self._connected = False
                raise

    async def close(self) -> None:
        """Auf Standby gehen, falls dieser Adapter gesteuert hat, dann die Verbindung schließen.

        Das Gerät hat keinen Watchdog (siehe Moduldoc). Die Freigabe (42000) bleibt an, sonst fiele
        es in seinen App-Modus und regelte selbst. Ein Fehlschlag hier darf das Entladen nicht
        aufhalten, deshalb nur ein Versuch und nur ein Logeintrag.
        """
        async with self._lock:
            if self._desired_force is not None and self._connected:
                try:
                    await self._request(
                        _FC_WRITE_SINGLE, _REG_FORCE_MODE, _FORCE_STANDBY, attempts=1
                    )
                except StorageAdapterError as exc:
                    _LOGGER.warning(
                        "Marstek %s:%s konnte beim Beenden nicht auf Standby gesetzt werden: %s",
                        self._host, self._port, exc,
                    )
            self._desired_force = None
            self._connected = False
            self._drop_connection()

    async def read(self) -> StorageState:
        # Nur lesen: die Freigabe darf hier nicht eingeschaltet werden (siehe Moduldoc).
        async with self._lock:
            self._require_connected()
            soc = await self._read_register(_REG_SOC)
            ac_power = _as_int16(await self._read_register(_REG_AC_POWER))
            control_mode = await self._read_register(_REG_CONTROL_MODE)
            force_mode = await self._read_register(_REG_FORCE_MODE)
            self._check_device_state(control_mode, force_mode)

        communication_interrupted = self._communication_interrupted
        self._communication_interrupted = False
        return StorageState(
            soc_percent=soc / 10,
            charge_power_w=float(max(-ac_power, 0)),
            discharge_power_w=float(max(ac_power, 0)),
            available=True,
            last_update=datetime.now(UTC),
            communication_interrupted=communication_interrupted,
        )

    def _check_device_state(self, control_mode: int, force_mode: int) -> None:
        """Abweichungen vom erwarteten Gerätezustand erkennen, damit der Sollwert neu kommt."""
        self._control_mode_on = control_mode == _CONTROL_MODE_ON
        if self._desired_force is None:
            return
        if self._control_mode_on and force_mode == self._desired_force:
            self._control_loss_logged = False
            return
        if self._control_mode_on:
            # Laut Suite (Issue 10) kann 42010 unter V150 kurz abweichend gelesen werden.
            _LOGGER.info(
                "Marstek %s:%s meldet Modus %s statt %s, der Sollwert wird erneut gesendet",
                self._host, self._port, force_mode, self._desired_force,
            )
        elif not self._control_loss_logged:
            self._control_loss_logged = True
            _LOGGER.warning(
                "Marstek %s:%s hat die Freigabe verloren (Register %s = %s), der Sollwert wird "
                "erneut gesendet",
                self._host, self._port, _REG_CONTROL_MODE, control_mode,
            )
        self._written.clear()
        self._communication_interrupted = True

    async def write_charge_power(self, watts: float) -> None:
        """Ladeleistung setzen. Wie über UDP gilt der zuletzt gesendete Sollwert (D-009)."""
        await self._apply(_FORCE_CHARGE, _REG_CHARGE_POWER, watts)

    async def write_discharge_power(self, watts: float) -> None:
        """Entladeleistung setzen. Wie über UDP gilt der zuletzt gesendete Sollwert (D-009)."""
        await self._apply(_FORCE_DISCHARGE, _REG_DISCHARGE_POWER, watts)

    async def _apply(self, active_mode: int, power_register: int, watts: float) -> None:
        power = min(abs(int(watts)), _MAX_POWER_W)
        force_mode = active_mode if power > 0 else _FORCE_STANDBY
        async with self._lock:
            self._require_connected()
            self._desired_force = force_mode
            if not self._control_mode_on:
                await self._write_register(_REG_CONTROL_MODE, _CONTROL_MODE_ON, force=True)
                self._control_mode_on = True
            # Erst die Leistung, dann der Modus: sonst liefe das Gerät kurz mit dem alten Wert an.
            if power > 0:
                await self._write_register(power_register, power)
            await self._write_register(_REG_FORCE_MODE, force_mode)

    def _require_connected(self) -> None:
        if not self._connected:
            raise StorageAdapterError("Adapter ist nicht verbunden — connect() nicht aufgerufen.")

    async def _read_register(self, register: int) -> int:
        reply = await self._request(_FC_READ_HOLDING, register, 1)
        if len(reply.payload) != 3 or reply.payload[0] != 2:
            raise StorageAdapterError(
                f"Marstek {self._host}:{self._port}: unerwartete Antwort auf Register {register}"
            )
        return int.from_bytes(reply.payload[1:3], "big")

    async def _write_register(self, register: int, value: int, *, force: bool = False) -> None:
        """Nur schreiben, was sich geändert hat oder länger her ist."""
        now = asyncio.get_running_loop().time()
        written = self._written.get(register)
        if (
            not force
            and written is not None
            and written[0] == value
            and now - written[1] < _REWRITE_AFTER_S
        ):
            return
        reply = await self._request(_FC_WRITE_SINGLE, register, value)
        if reply.payload != struct.pack(">HH", register, value):
            raise StorageAdapterError(
                f"Marstek {self._host}:{self._port}: Register {register} nicht bestätigt"
            )
        self._written[register] = (value, asyncio.get_running_loop().time())

    async def _request(
        self, function: int, register: int, word: int, *, attempts: int | None = None
    ) -> _Reply:
        """Eine Anfrage samt Wiederholung. Der Aufrufer hält `self._lock`."""
        loop = asyncio.get_running_loop()
        started = loop.time()
        # Im laufenden Aussetzer genügt ein Versuch, sonst stauen sich wartende Aufrufe (D-021).
        if attempts is None:
            attempts = 1 if self._silent_since is not None else _REQUEST_ATTEMPTS
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                await self._ensure_open()
                await self._wait_for_request_slot()
                try:
                    reply = await self._transact(function, register, word)
                finally:
                    self._last_request_finished = loop.time()
            except _DeviceRefused:
                # Das Gerät hat geantwortet, die Verbindung bleibt im Takt.
                self._note_reply(register, attempt, started)
                raise
            except (TimeoutError, OSError, EOFError, ValueError, StorageAdapterError) as exc:
                last_error = exc
                self._drop_connection()
                _LOGGER.debug(
                    "Marstek %s:%s antwortet nicht auf Register %s (Versuch %s/%s): %s",
                    self._host, self._port, register, attempt, attempts, exc,
                )
                continue
            except BaseException:
                # Abbruch mitten in der Anfrage: die Antwort käme sonst bei der nächsten an.
                self._drop_connection()
                raise
            self._note_reply(register, attempt, started)
            return reply

        if self._silent_since is None:
            self._silent_since = started
        self._communication_interrupted = True
        versuche = "einem Versuch" if attempts == 1 else f"{attempts} Versuchen"
        raise StorageAdapterError(
            f"Marstek {self._host}:{self._port} antwortet nach {versuche} nicht auf "
            f"Register {register}."
        ) from last_error

    def _note_reply(self, register: int, attempt: int, started: float) -> None:
        """Aussetzer nach einer Antwort festhalten und fürs Info-Log messen (D-021)."""
        now = asyncio.get_running_loop().time()
        if attempt > 1:
            self._communication_interrupted = True
        if attempt > 1 or now - started >= _SLOW_REPLY_S:
            _LOGGER.info(
                "Marstek %s:%s antwortet auf Register %s erst nach %.1f s (Versuch %s)",
                self._host, self._port, register, now - started, attempt,
            )
        if self._silent_since is not None:
            self._communication_interrupted = True
            _LOGGER.info(
                "Marstek %s:%s antwortet nach %.1f s Aussetzer wieder",
                self._host, self._port, now - self._silent_since,
            )
            self._silent_since = None

    async def _wait_for_request_slot(self) -> None:
        if self._last_request_finished is None:
            return
        wait = _MESSAGE_WAIT_S - (asyncio.get_running_loop().time() - self._last_request_finished)
        if wait > 0:
            await asyncio.sleep(wait)

    async def _ensure_open(self) -> None:
        if self._writer is not None and not self._writer.is_closing():
            return
        self._drop_connection()
        loop = asyncio.get_running_loop()
        if loop.time() < self._connect_not_before:
            raise StorageAdapterError(
                f"Marstek {self._host}:{self._port}: nächster Verbindungsversuch noch gesperrt"
            )
        # Das Gerät nimmt direkt nach dem Schließen keine neue Verbindung an (laut Suite gemessen).
        if self._last_closed is not None:
            wait = _RECONNECT_SETTLE_S - (loop.time() - self._last_closed)
            if wait > 0:
                await asyncio.sleep(wait)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), _REQUEST_TIMEOUT_S
            )
        except (TimeoutError, OSError) as exc:
            # Ein Gerät im Reset nicht mit Verbindungsversuchen überhäufen.
            backoff = min(
                _CONNECT_BACKOFF_BASE_S * 2**self._connect_failures, _CONNECT_BACKOFF_MAX_S
            )
            self._connect_failures += 1
            self._connect_not_before = loop.time() + backoff
            raise StorageAdapterError(
                f"Marstek-Gerät {self._host}:{self._port} nicht erreichbar: {exc}"
            ) from exc
        self._connect_failures = 0
        self._connect_not_before = 0.0

    def _drop_connection(self) -> None:
        """Socket verwerfen. Danach ist nicht mehr sicher, was am Gerät gilt."""
        if self._writer is not None:
            self._writer.close()
            self._last_closed = asyncio.get_running_loop().time()
        self._reader = None
        self._writer = None
        self._written.clear()
        self._control_mode_on = None

    async def _transact(self, function: int, register: int, word: int) -> _Reply:
        self._transaction_id = self._transaction_id % _MAX_TRANSACTION_ID + 1
        transaction_id = self._transaction_id
        self._writer.write(
            struct.pack(
                ">HHHBBHH", transaction_id, 0, 6, _UNIT_ID, function, register, word
            )
        )
        async with asyncio.timeout(_REQUEST_TIMEOUT_S):
            await self._writer.drain()
            while True:
                received_id, reply = await self._read_frame()
                if received_id == transaction_id:
                    break
                # Verspätete Antwort auf einen früheren Versuch: Reihenfolge bleibt erhalten.
                _LOGGER.debug(
                    "Marstek %s:%s: verspätete Antwort %s verworfen (erwartet %s)",
                    self._host, self._port, received_id, transaction_id,
                )
        if reply.function & _EXCEPTION_BIT:
            raise _DeviceRefused(
                f"Marstek {self._host}:{self._port} lehnt Register {register} ab "
                f"(Fehlercode {reply.payload[0]})"
            )
        if reply.function != function:
            raise ValueError(f"Antwort mit Funktion {reply.function} auf {function}")
        return reply

    async def _read_frame(self) -> tuple[int, _Reply]:
        header = await self._reader.readexactly(_MBAP_SIZE)
        transaction_id, protocol, length, _unit = struct.unpack(">HHHB", header)
        if protocol != 0 or not 2 <= length <= _MAX_MBAP_LENGTH:
            raise ValueError(f"Ungültiger Modbus-Kopf: {header.hex()}")
        function = (await self._reader.readexactly(1))[0]
        # Fehlerantworten nicht nach dem Kopf bemessen, siehe Moduldoc.
        remaining = 1 if function & _EXCEPTION_BIT else length - 2
        payload = await self._reader.readexactly(remaining)
        return transaction_id, _Reply(function, payload)


def _as_int16(value: int) -> int:
    return value - 0x10000 if value >= 0x8000 else value
