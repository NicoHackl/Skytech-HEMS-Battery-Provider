"""Marstek Local API — UDP-JSON-RPC-Adapter (Lese- und Schreibzugriff).

Protokoll-Referenz — von Marstek nicht offiziell veröffentlicht, aus vier unabhängigen
Community-Quellen zusammengetragen (siehe docs/bekannte-luecken.md für Details, Quellenlage
und die verbleibenden offenen Punkte):
- https://github.com/Randyocean/Marstek/blob/main/docs/marstek_device_openapi.MD (Protokoll-Dump)
- https://github.com/taurgis/has-marstek-local-api (Venus E 3.0 ausdrücklich unterstützt,
  Venus E2.0 ausdrücklich NICHT)
- https://github.com/jaapp/ha-marstek-local-api
- https://github.com/leonscheltema/ha-marstek

Schreibzugriff läuft über `ES.SetMode` im Passive-Mode (`passive_cfg: {power, cd_time}`) — nicht
über Manual-Mode-Zeitfenster: alle vier Quellen setzen für einen direkten Leistungs-Sollwert
übereinstimmend auf Passive-Mode, Manual-Mode ist für feste Tageszeitpläne gedacht. `cd_time`
ist ein Sicherheits-Watchdog: läuft er ab, ohne dass ein neuer Sollwert kommt, fällt das Gerät
zurück in den vorherigen Modus — kein Sollwert bleibt für immer erzwungen, wenn HA nicht mehr
antwortet. **Trotzdem unverifiziert an echter Hardware** (Plan Abschnitt 5, M1-Abnahme) — vor dem
produktiven Einsatz prüfen, siehe docs/bekannte-luecken.md.

Verbindungsabbruch und Neuaufbau: Der UDP-Transport wird nicht mehr nur einmal beim Einrichten
erzeugt. Home Assistant ruft `connect()` von sich aus genau einmal auf (über
`coordinator._async_setup()`, das nur beim ersten Refresh läuft) — stirbt der Socket danach, bleibt
er tot, und `sendto()` verpufft ab da still, ohne Exception. Am 10.09.2026 lief die Anbindung so
96 Minuten ins Leere (04:09 bis 05:45), obwohl das Gerät erreichbar war: der erste Schreibvorgang
auf einem frisch erzeugten Socket war unmittelbar nach dem Neuladen der Integration erfolgreich.
Deshalb prüft dieser Adapter vor jedem Aufruf selbst, ob der Transport noch lebt
(`connection_lost`, `is_closing()`), und verwirft ihn zusätzlich nach
`_RECONNECT_AFTER_FAILED_CALLS` erfolglosen Aufrufen — der Neuaufbau vergibt einen neuen Quellport
und entspricht damit dem, was bisher nur ein manuelles Neuladen bewirkt hat. Details:
docs/bekannte-luecken.md, Abschnitt „Verbindung reißt ab" und docs/adr/D-013-udp-reconnect.md.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
from datetime import UTC, datetime
from typing import Any

from ..models import StorageState
from .base import StorageAdapterError

_LOGGER = logging.getLogger(__name__)

_METHOD_ES_GET_STATUS = "ES.GetStatus"
_METHOD_ES_SET_MODE = "ES.SetMode"
_REQUEST_TIMEOUT_S = 1.0
_REQUEST_RETRIES = 3
# Nach so vielen aufeinanderfolgend erfolglosen Aufrufen wird der UDP-Transport verworfen und beim
# nächsten Aufruf neu aufgebaut (siehe Moduldoc). Ein erfolgloser Aufruf dauert bereits
# `_REQUEST_RETRIES` × `_REQUEST_TIMEOUT_S`; zwei davon hintereinander sind damit wenige Sekunden —
# träge genug, dass ein einzelnes verlorenes Paket nicht sofort einen neuen Socket erzwingt, und
# schnell genug, um weit unter dem 300-s-Watchdog des Passive-Mode zu bleiben.
_RECONNECT_AFTER_FAILED_CALLS = 2
# Sicherheits-Watchdog für den Passive-Mode-Sollwert (siehe Moduldoc) — Default von
# leonscheltema/ha-marstek übernommen, dort ebenfalls der Standardwert der Entity.
_PASSIVE_MODE_DURATION_S = 300


class _MarstekUdpProtocol(asyncio.DatagramProtocol):
    """Reicht eingehende Datagramme an eine Queue durch — ein Request ist immer am Leben."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        # Lässt asyncio den Transport fallen, verpufft jedes weitere `sendto()` still — ohne
        # Exception, ohne Rückmeldung. Dieser Merker ist die einzige Stelle, an der das überhaupt
        # sichtbar wird (siehe Moduldoc, Vorfall vom 10.09.2026).
        self.lost = False
        self.last_error: Exception | None = None

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        self.last_error = exc
        _LOGGER.debug("UDP-Fehler vom Marstek-Gerät: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        self.lost = True
        if exc is None:
            # Regulärer close() beim Entladen der Integration — kein Fehlerfall.
            _LOGGER.debug("UDP-Verbindung zum Marstek-Gerät regulär geschlossen.")
            return
        _LOGGER.warning("UDP-Verbindung zum Marstek-Gerät unerwartet beendet: %s", exc)


class MarstekUdpAdapter:
    """`StorageAdapter`-Implementierung für die Marstek Local API (UDP JSON-RPC)."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: _MarstekUdpProtocol | None = None
        # Eine Request-ID je Aufruf, über die gesamte Adapter-Lebensdauer fortlaufend —
        # verhindert, dass eine verspätete Antwort auf einen früheren Request als aktuell
        # durchgeht.
        self._request_ids = itertools.count(1)
        # Serialisiert alle _call()-Aufrufe: Coordinator-Poll (read()) und HEMS-Anbindung
        # (write_charge_power()/write_discharge_power(), auf demselben Adapter, aber als
        # eigener, event-getriebener Task) griffen sonst gleichzeitig auf dieselbe
        # Antwort-Queue zu. Eine fremde Antwort wird dort per `continue` verworfen statt
        # zurückgelegt — der eigentliche Empfänger sieht sie nie und timeoutet, obwohl das
        # Gerät korrekt geantwortet hat. Ohne Lock erklärt das genau das beobachtete Muster:
        # ES.SetMode (sehr häufig durch die HEMS-Anbindung ausgelöst) timeoutet praktisch
        # immer, ES.GetStatus (fester 5-s-Takt) nur gelegentlich.
        self._call_lock = asyncio.Lock()
        # Ob überhaupt schon einmal `connect()` lief. Bewusst getrennt vom Zustand des Transports:
        # ein toter Transport wird selbst neu aufgebaut, ein nie verbundener Adapter meldet
        # dagegen weiterhin einen sprechenden Fehler statt still eine Verbindung aufzumachen.
        self._connected = False
        # Aufeinanderfolgend erfolglose Aufrufe, siehe `_RECONNECT_AFTER_FAILED_CALLS`.
        self._failed_calls = 0
        # Ob der Neuaufbau in der laufenden Ausfallphase schon gemeldet wurde, siehe
        # `_log_reconnect()`.
        self._reconnect_logged = False

    async def connect(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            self._transport, self._protocol = await loop.create_datagram_endpoint(
                _MarstekUdpProtocol,
                remote_addr=(self._host, self._port),
            )
        except OSError as exc:
            raise StorageAdapterError(
                f"Marstek-Gerät {self._host}:{self._port} nicht erreichbar: {exc}"
            ) from exc
        self._connected = True
        self._failed_calls = 0

    async def close(self) -> None:
        self._close_transport()
        self._connected = False
        self._failed_calls = 0
        self._reconnect_logged = False

    def _close_transport(self) -> None:
        """Nur den Transport wegwerfen — der Adapter gilt weiterhin als verbunden.

        Gegenstück zu `close()`: dort endet die Adapter-Lebensdauer (Entry wird entladen), hier
        wird lediglich ein unbrauchbar gewordener Socket verworfen, damit der nächste Aufruf
        einen frischen erzeugt.
        """
        if self._transport is not None:
            self._transport.close()
        self._transport = None
        self._protocol = None

    def _is_connection_dead(self) -> bool:
        """Ob der aktuelle Transport nicht mehr benutzbar ist."""
        return (
            self._transport is None
            or self._protocol is None
            or self._protocol.lost
            or self._transport.is_closing()
        )

    async def _async_ensure_connection(self) -> None:
        """Vor jedem Aufruf sicherstellen, dass ein lebender Transport da ist (siehe Moduldoc)."""
        if not self._is_connection_dead():
            return
        if self._transport is not None:
            # Der Transport hat sich selbst verabschiedet — genau der Fall, der bisher gar nicht
            # auffiel. Wurde er dagegen weiter unten selbst verworfen, ist das schon gemeldet.
            self._log_reconnect("der bisherige Socket ist nicht mehr benutzbar")
        self._close_transport()
        await self.connect()

    def _log_reconnect(self, reason: str) -> None:
        """Den Neuaufbau melden: einmal je Ausfallphase deutlich, danach nur noch im Debug-Log.

        Ein stundenlanger Ausfall soll nicht dieselbe Zeile im Minutentakt ins Log schreiben —
        derselbe Gedanke wie bei den Schreibfehlern in `hems_bridge.py`.
        """
        message = "Verbindung zum Marstek-Gerät %s:%s wird neu aufgebaut: %s"
        if self._reconnect_logged:
            _LOGGER.debug(message, self._host, self._port, reason)
            return
        self._reconnect_logged = True
        _LOGGER.warning(message, self._host, self._port, reason)

    async def read(self) -> StorageState:
        result = await self._call(_METHOD_ES_GET_STATUS, {"id": 0})
        if "bat_power" in result:
            charge_power_w, discharge_power_w = _split_bat_power(result.get("bat_power"))
        else:
            # Laut Marstek-Protokoll-Doku ist `bat_power` ein reguläres Feld von ES.GetStatus —
            # fehlt es trotzdem (an dieser Anlage durchgängig beobachtet, siehe
            # docs/bekannte-luecken.md), ist das kein geratener Sonderfall, sondern ein
            # bislang unbeobachtetes Live-Verhalten. Rohantwort loggen statt zu raten, siehe
            # Regel 7 (AGENTS.md „Nicht raten").
            _LOGGER.debug(
                "ES.GetStatus von %s:%s ohne Feld 'bat_power' — Rohantwort: %r",
                self._host, self._port, result,
            )
            # Ersatzweise `ongrid_power`: an dieser Anlage die einzige verfügbare Annäherung an
            # die Ist-Leistung (vom User an echter Hardware beobachtet, nicht aus offizieller
            # Doku). Deckt nur den Netz-Anteil ab, keinen Offgrid-/Backup-Anteil
            # (`offgrid_power`, hier bislang immer 0) — bei aktivem Backup-Kreis würde ein Teil
            # der tatsächlichen Batterieleistung fehlen. Vorzeichen umgekehrt zu `bat_power`:
            # `ongrid_power` positiv heißt „speist ins Netz ein" (= entladen), negativ heißt
            # „bezieht vom Netz" (= laden) — deshalb negiert, bevor es in dieselbe Aufteilung wie
            # `bat_power` geht. Weiterhin nicht offiziell bestätigt, siehe bekannte-luecken.md.
            ongrid_power = _as_float(result.get("ongrid_power"))
            fallback_bat_power = -ongrid_power if ongrid_power is not None else None
            charge_power_w, discharge_power_w = _split_bat_power(fallback_bat_power)
        return StorageState(
            soc_percent=_as_float(result.get("bat_soc")),
            charge_power_w=charge_power_w,
            discharge_power_w=discharge_power_w,
            available=True,
            last_update=datetime.now(UTC),
        )

    async def write_charge_power(self, watts: float) -> None:
        """Ladeleistung setzen — Passive Mode, `power` negativ = laden (siehe Moduldoc)."""
        await self._set_passive_power(-watts)

    async def write_discharge_power(self, watts: float) -> None:
        """Entladeleistung setzen — Passive Mode, `power` positiv = entladen (siehe Moduldoc)."""
        await self._set_passive_power(watts)

    async def _set_passive_power(self, power: float) -> None:
        result = await self._call(
            _METHOD_ES_SET_MODE,
            {
                "id": 0,
                "config": {
                    "mode": "Passive",
                    "passive_cfg": {
                        "power": int(power),
                        "cd_time": _PASSIVE_MODE_DURATION_S,
                    },
                },
            },
        )
        if not result.get("set_result"):
            raise StorageAdapterError(f"Marstek-Gerät hat den Sollwert abgelehnt: {result!r}")

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._connected:
            raise StorageAdapterError("Adapter ist nicht verbunden — connect() nicht aufgerufen.")

        # Serialisiert — siehe Kommentar zu `_call_lock` in __init__(). Ohne diesen Lock teilen
        # sich ein gleichzeitiger read() (Coordinator) und write_*() (HEMS-Anbindung) dieselbe
        # Antwort-Queue und können sich gegenseitig die Antwort stehlen.
        async with self._call_lock:
            return await self._call_locked(method, params)

    async def _call_locked(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        await self._async_ensure_connection()
        # Verspätete Antworten auf einen früheren, längst abgelaufenen Request liegen sonst noch
        # in der Queue. Die id-Prüfung unten würde sie zwar verwerfen, aber erst nachdem sie aus
        # der Queue geholt wurden — einmal vorab leerräumen ist billiger und eindeutiger.
        queue = self._protocol.queue
        while not queue.empty():
            queue.get_nowait()

        request_id = next(self._request_ids)
        payload = json.dumps({"id": request_id, "method": method, "params": params}).encode()
        loop = asyncio.get_running_loop()
        last_error: Exception | None = None

        for attempt in range(1, _REQUEST_RETRIES + 1):
            self._transport.sendto(payload)
            deadline = loop.time() + _REQUEST_TIMEOUT_S

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    last_error = TimeoutError(f"Keine Antwort auf {method} innerhalb 1 s")
                    break
                try:
                    data = await asyncio.wait_for(self._protocol.queue.get(), timeout=remaining)
                except TimeoutError as exc:
                    last_error = exc
                    break

                try:
                    response = json.loads(data)
                except json.JSONDecodeError:
                    continue  # unlesbares Paket, ohne Retry weiter auf die echte Antwort warten

                if response.get("id") != request_id:
                    continue  # verspätete Antwort auf einen älteren Request, verwerfen

                # Ab hier hat das Gerät nachweislich geantwortet — auch eine Fehlerantwort ist
                # ein Lebenszeichen des Transports. Damit endet die Ausfallphase: Zähler und
                # Melde-Sperre gehören zurückgesetzt.
                self._failed_calls = 0
                self._reconnect_logged = False
                if "result" not in response:
                    raise StorageAdapterError(
                        f"Marstek-Gerät meldet einen Fehler auf {method}: {response!r}"
                    )
                return response["result"]

            _LOGGER.debug(
                "Marstek %s:%s antwortet nicht auf %s (Versuch %s/%s)",
                self._host, self._port, method, attempt, _REQUEST_RETRIES,
            )

        self._failed_calls += 1
        if self._failed_calls >= _RECONNECT_AFTER_FAILED_CALLS:
            self._log_reconnect(
                f"das Gerät antwortet seit {self._failed_calls} Aufrufen nicht"
            )
            self._close_transport()
            self._failed_calls = 0

        raise StorageAdapterError(
            f"Marstek {self._host}:{self._port} antwortet nach {_REQUEST_RETRIES} Versuchen "
            f"nicht auf {method}."
        ) from last_error


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_bat_power(raw: Any) -> tuple[float | None, float | None]:
    """Signierte `bat_power` in `charge_power_w`/`discharge_power_w` (je ≥ 0) aufteilen.

    Vorzeichenkonvention **unverifiziert** — siehe docs/bekannte-luecken.md. Übernommen aus
    taurgis/has-marstek-local-api: `bat_power` positiv = laden, negativ = entladen (dort für
    die eigene, umgekehrte HA-Konvention negiert). Vor dem produktiven Einsatz an echter
    Hardware bestätigen (Plan Abschnitt 5, M1-Abnahme).
    """
    value = _as_float(raw)
    if value is None:
        return None, None
    if value >= 0:
        return value, 0.0
    return 0.0, -value
