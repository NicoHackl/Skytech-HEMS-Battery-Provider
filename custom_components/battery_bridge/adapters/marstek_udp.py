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
# Sicherheits-Watchdog für den Passive-Mode-Sollwert (siehe Moduldoc) — Default von
# leonscheltema/ha-marstek übernommen, dort ebenfalls der Standardwert der Entity.
_PASSIVE_MODE_DURATION_S = 300


class _MarstekUdpProtocol(asyncio.DatagramProtocol):
    """Reicht eingehende Datagramme an eine Queue durch — ein Request ist immer am Leben."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.queue.put_nowait(data)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("UDP-Fehler vom Marstek-Gerät: %s", exc)


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

    async def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
        self._transport = None
        self._protocol = None

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
        if self._transport is None or self._protocol is None:
            raise StorageAdapterError("Adapter ist nicht verbunden — connect() nicht aufgerufen.")

        # Serialisiert — siehe Kommentar zu `_call_lock` in __init__(). Ohne diesen Lock teilen
        # sich ein gleichzeitiger read() (Coordinator) und write_*() (HEMS-Anbindung) dieselbe
        # Antwort-Queue und können sich gegenseitig die Antwort stehlen.
        async with self._call_lock:
            return await self._call_locked(method, params)

    async def _call_locked(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
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

                if "result" not in response:
                    raise StorageAdapterError(
                        f"Marstek-Gerät meldet einen Fehler auf {method}: {response!r}"
                    )
                return response["result"]

            _LOGGER.debug(
                "Marstek %s:%s antwortet nicht auf %s (Versuch %s/%s)",
                self._host, self._port, method, attempt, _REQUEST_RETRIES,
            )

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
