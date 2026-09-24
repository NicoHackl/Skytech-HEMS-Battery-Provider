"""E3DC-Hauskraftwerk — RSCP-Adapter über die Bibliothek pye3dc (Lese- und Schreibzugriff, D-015).

Lesen: `E3DC.poll()` liefert SoC (`stateOfCharge`) und die Batterieleistung
(`consumption.battery`, positiv = laden, negativ = entladen — laut pye3dc-Doku).

Schreiben: RSCP `EMS_REQ_SET_POWER` mit Betriebsart und Leistung — derselbe Weg, den das bisherige
pyscript `e3dc_start_manual_power` in Home Assistant nutzt. Abbildung (vom User festgelegt am
23.09.2026):
- Soll-Ladeleistung > 0 → Betriebsart 4 „Netzladen" (lädt den Sollwert, notfalls aus dem Netz,
  wie der Passive-Mode bei Marstek)
- Soll-Entladeleistung > 0 → Betriebsart 2 „Entladen"
- Sollwert 0 → Betriebsart 1 „Leerlauf" (weder laden noch entladen)

Wie bei Marstek steuern `write_charge_power()` und `write_discharge_power()` denselben einzigen
Sollwert — der zuletzt gesendete Aufruf gilt vollständig. E3DC hält einen solchen Sollwert nur
rund 10 s und übernimmt dann selbst wieder die Regelung; die HEMS-Anbindung sendet deshalb im
Takt von `keepalive_interval` (5 s) erneut (hems_bridge.py).

pye3dc arbeitet synchron mit blockierenden Sockets — jeder Aufruf läuft deshalb im Executor, und
ein Lock serialisiert Coordinator-Poll und HEMS-Schreibvorgänge auf derselben RSCP-Sitzung.
Verbindungsabbrüche heilt pye3dc selbst: nach einem Fehler trennt die Bibliothek die Sitzung und
baut sie beim nächsten Aufruf neu auf (inklusive Anmeldung). Ein eigener Neuaufbau wie bei Marstek
(D-013) ist hier nicht nötig.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, TypeVar

from e3dc import E3DC, AuthenticationError, RSCPKeyError

from ..const import E3DC_KEEPALIVE_INTERVAL
from ..models import StorageState
from .base import StorageAdapterAuthError, StorageAdapterError

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

# Betriebsarten von EMS_REQ_SET_POWER_MODE (RSCP-Dokumentation E3DC, identisch zum pyscript).
_MODE_IDLE = 1
_MODE_DISCHARGE = 2
_MODE_GRID_CHARGE = 4

# Ersatz-Obergrenze, falls das Gerät seine maximale Lade-/Entladeleistung nicht meldet. Liegt über
# den größten Hauskraftwerken (S10X), damit nichts Gültiges abgeschnitten wird — die tatsächliche
# Grenze setzt das Gerät selbst.
_FALLBACK_MAX_POWER_W = 12000


class E3dcRscpAdapter:
    """`StorageAdapter`-Implementierung für E3DC-Hauskraftwerke (RSCP, lokal)."""

    keepalive_interval = E3DC_KEEPALIVE_INTERVAL

    def __init__(self, host: str, port: int, username: str, password: str, rscp_key: str) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._rscp_key = rscp_key
        self._e3dc: E3DC | None = None
        # Serialisiert alle Aufrufe auf die eine RSCP-Sitzung — pye3dc ist nicht threadsicher,
        # Coordinator-Poll und HEMS-Anbindung laufen aber als getrennte Tasks.
        self._call_lock = asyncio.Lock()

    @property
    def serial_number(self) -> str | None:
        """Seriennummer des Hauskraftwerks — erst nach `connect()` bekannt, für die unique_id."""
        if self._e3dc is None or not self._e3dc.serialNumber:
            return None
        return f"{self._e3dc.serialNumberPrefix or ''}{self._e3dc.serialNumber}"

    @property
    def max_power_w(self) -> int:
        """Größere der vom Gerät gemeldeten Grenzen für Laden/Entladen, sonst Ersatzwert."""
        if self._e3dc is None:
            return _FALLBACK_MAX_POWER_W
        limits = [
            int(value)
            for value in (self._e3dc.maxBatChargePower, self._e3dc.maxBatDischargePower)
            if isinstance(value, int | float) and value > 0
        ]
        return max(limits) if limits else _FALLBACK_MAX_POWER_W

    async def connect(self) -> None:
        # Der pye3dc-Konstruktor meldet sich bereits an und liest die Anlagenkennung — also
        # Netzwerkzugriff, deshalb ebenfalls im Executor.
        self._e3dc = await self._run(self._create_client, "Verbindungsaufbau")

    def _create_client(self) -> E3DC:
        return E3DC(
            E3DC.CONNECT_LOCAL,
            username=self._username,
            password=self._password,
            ipAddress=self._host,
            key=self._rscp_key,
            port=self._port,
        )

    async def close(self) -> None:
        client = self._e3dc
        self._e3dc = None
        if client is None:
            return
        try:
            await asyncio.get_running_loop().run_in_executor(None, client.disconnect)
        except Exception as exc:  # noqa: BLE001 — Aufräumen darf das Entladen nie verhindern
            _LOGGER.debug("Trennen vom E3DC-Gerät %s fehlgeschlagen: %s", self._host, exc)

    async def read(self) -> StorageState:
        client = self._require_client()
        result = await self._run(lambda: client.poll(keepAlive=True), "Abfrage")
        consumption = result.get("consumption") or {}
        charge_power_w, discharge_power_w = _split_battery_power(consumption.get("battery"))
        return StorageState(
            soc_percent=_as_float(result.get("stateOfCharge")),
            charge_power_w=charge_power_w,
            discharge_power_w=discharge_power_w,
            available=True,
            last_update=datetime.now(UTC),
        )

    async def write_charge_power(self, watts: float) -> None:
        """Ladeleistung setzen — > 0 Netzladen, 0 Leerlauf (siehe Moduldoc)."""
        await self._set_power(_MODE_GRID_CHARGE if watts > 0 else _MODE_IDLE, watts)

    async def write_discharge_power(self, watts: float) -> None:
        """Entladeleistung setzen — > 0 Entladen, 0 Leerlauf (siehe Moduldoc)."""
        await self._set_power(_MODE_DISCHARGE if watts > 0 else _MODE_IDLE, watts)

    async def _set_power(self, mode: int, watts: float) -> None:
        client = self._require_client()
        value = int(watts) if mode != _MODE_IDLE else 0
        # Tag- und Typnamen als Text — pye3dc löst sie selbst auf, ohne dass wir auf ihr
        # internes Tag-Modul zugreifen müssen.
        request = (
            "EMS_REQ_SET_POWER",
            "Container",
            [
                ("EMS_REQ_SET_POWER_MODE", "UChar8", mode),
                ("EMS_REQ_SET_POWER_VALUE", "Int32", value),
            ],
        )
        response = await self._run(
            lambda: client.sendRequest(request, keepAlive=True), "Sollwert setzen"
        )
        # Ein abgelehnter Befehl kommt als RSCP-Fehler zurück, den pye3dc bereits als Exception
        # wirft. Die Antwort selbst nur fürs Debugging festhalten.
        _LOGGER.debug(
            "E3DC %s: Betriebsart %s, %s W gesetzt — Antwort: %r", self._host, mode, value, response
        )

    def _require_client(self) -> E3DC:
        if self._e3dc is None:
            raise StorageAdapterError("Adapter ist nicht verbunden — connect() nicht aufgerufen.")
        return self._e3dc

    async def _run(self, func: Callable[[], _T], action: str) -> _T:
        """Blockierenden pye3dc-Aufruf im Executor ausführen und Fehler vereinheitlichen."""
        async with self._call_lock:
            try:
                return await asyncio.get_running_loop().run_in_executor(None, func)
            except (AuthenticationError, RSCPKeyError) as exc:
                # RSCPKeyError: das Gerät schließt die Verbindung wortlos — bei E3DC das Zeichen
                # für einen falschen RSCP-Schlüssel.
                raise StorageAdapterAuthError(
                    f"E3DC-Gerät {self._host} lehnt die Zugangsdaten ab ({action}): "
                    f"{type(exc).__name__}"
                ) from exc
            except Exception as exc:
                # pye3dc wirft je nach Fehlerort unterschiedliche Typen (SendError,
                # CommunicationError, OSError, aber auch KeyError/TypeError bei unerwarteten
                # Antworten) — an dieser Bibliotheksgrenze einheitlich übersetzen.
                raise StorageAdapterError(
                    f"E3DC-Gerät {self._host}:{self._port} — {action} fehlgeschlagen: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_battery_power(raw: Any) -> tuple[float | None, float | None]:
    """Signierte Batterieleistung (positiv = laden) in Lade-/Entladeleistung (je ≥ 0) aufteilen."""
    value = _as_float(raw)
    if value is None:
        return None, None
    if value >= 0:
        return value, 0.0
    return 0.0, -value
