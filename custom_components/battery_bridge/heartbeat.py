"""heartbeat.py — Auswertung des SkytechHEMS-Lebenszeichens (D-016).

SkytechHEMS veröffentlicht nach jedem Regelzyklus `sensor.skytech_hems_status`; `state` ist ein
Zykluszähler, der sich bei jeder Veröffentlichung ändert. Ein unverändert bleibender
Sollwerthelfer ist dagegen normaler Betrieb und taugt nicht als Lebenszeichen. Vertrag:
`contract/contract_hems_battery_provider/contract_hems_battery_provider.md`, Abschnitt
„HEMS-Lebenszeichen".

Regeln aus dem Vertrag:

- Gemessen wird mit der **eigenen** monotonen Uhr, wann zuletzt eine Änderung des Zählers gesehen
  wurde. `erzeugt_am` und die Uhr des HEMS werden nie ausgewertet.
- Frisch, solange die letzte Änderung höchstens `faktor × zyklus_intervall_s` zurückliegt; fehlt
  das Intervall oder ist es ungültig, gelten 90 s.
- Der beim Start vorgefundene Wert ist nur die Ausgangslage. Frisch wird das Lebenszeichen erst
  nach einer Änderung, die **nach** dem Start gesehen wurde — ein wiederhergestellter oder alter
  Wert löst keine Ladung aus.
- Fehlt die Entität oder ist sie `unknown`/`unavailable`, ist das Lebenszeichen nicht frisch.

Bewusst ohne Home-Assistant-Import: die Regeln sind reine Logik und so ohne HA-Instanz testbar.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping
from typing import Any, Final

STATUS_ENTITY_ID: Final = "sensor.skytech_hems_status"
FALLBACK_TIMEOUT_S: Final = 90.0
DEFAULT_TIMEOUT_FACTOR: Final = 3
MIN_TIMEOUT_FACTOR: Final = 2
MAX_TIMEOUT_FACTOR: Final = 10

_INVALID_STATES: Final = frozenset({"unknown", "unavailable", ""})


class HemsHeartbeat:
    """Merkt sich die letzte gesehene Zähleränderung und beurteilt die Frische."""

    def __init__(
        self, timeout_factor: float, clock: Callable[[], float] | None = None
    ) -> None:
        self._factor = float(timeout_factor)
        # Zur Laufzeit nachgeschlagen, damit Tests die Uhr des Moduls ersetzen können.
        self._clock = clock or (lambda: time.monotonic())
        self._started = False
        self._last_value: str | None = None
        self._last_change_at: float | None = None
        self._interval_s: float | None = None

    @property
    def timeout_s(self) -> float:
        """Aktuelle Frist in Sekunden."""
        if self._interval_s is None:
            return FALLBACK_TIMEOUT_S
        return self._factor * self._interval_s

    def observe(self, state: str | None, attributes: Mapping[str, Any] | None = None) -> None:
        """Einen gelesenen Zustand der Statusentität verarbeiten (`None` = Entität fehlt)."""
        value = None if state is None or state in _INVALID_STATES else state
        self._interval_s = _parse_interval((attributes or {}).get("zyklus_intervall_s"))
        if not self._started:
            # Ausgangslage beim Start — nie selbst ein Beleg für einen frischen Zyklus.
            self._started = True
            self._last_value = value
            return
        if value is not None and value != self._last_value:
            self._last_change_at = self._clock()
        self._last_value = value

    def is_fresh(self) -> bool:
        """Ob seit dem Start ein Zyklus gesehen wurde und er innerhalb der Frist liegt."""
        if self._last_value is None or self._last_change_at is None:
            return False
        return self._clock() - self._last_change_at <= self.timeout_s


def _parse_interval(raw: Any) -> float | None:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return value
