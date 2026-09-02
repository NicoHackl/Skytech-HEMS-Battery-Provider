"""Marstek Local API — UDP-JSON-RPC-Adapter (Lesezugriff, M1).

Protokoll-Referenz — von Marstek nicht offiziell veröffentlicht, aus Community-Quellen
zusammengetragen (siehe docs/bekannte-luecken.md für Details und offene Punkte):
- https://github.com/Randyocean/Marstek/blob/main/docs/marstek_device_openapi.MD
- https://github.com/taurgis/has-marstek-local-api (aktiv gepflegte Referenzintegration,
  Venus E 3.0 ausdrücklich unterstützt, Venus E2.0 ausdrücklich NICHT)

Schreibzugriff (`write_charge_power`/`write_discharge_power`) ist bewusst noch nicht
implementiert — welcher Mechanismus (Passive-Mode-Sollwert vs. Manual-Mode-Zeitfenster) auf
echter Hardware tatsächlich sicher funktioniert, ist ungeklärt (Plan Abschnitt 5, M2).
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
_REQUEST_TIMEOUT_S = 1.0
_REQUEST_RETRIES = 3


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
        charge_power_w, discharge_power_w = _split_bat_power(result.get("bat_power"))
        return StorageState(
            soc_percent=_as_float(result.get("bat_soc")),
            charge_power_w=charge_power_w,
            discharge_power_w=discharge_power_w,
            available=True,
            last_update=datetime.now(UTC),
        )

    async def write_charge_power(self, watts: float) -> None:
        raise NotImplementedError(
            "Schreibzugriff auf die Marstek Local API ist noch nicht implementiert — "
            "siehe docs/bekannte-luecken.md."
        )

    async def write_discharge_power(self, watts: float) -> None:
        raise NotImplementedError(
            "Schreibzugriff auf die Marstek Local API ist noch nicht implementiert — "
            "siehe docs/bekannte-luecken.md."
        )

    async def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._transport is None or self._protocol is None:
            raise StorageAdapterError("Adapter ist nicht verbunden — connect() nicht aufgerufen.")

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
