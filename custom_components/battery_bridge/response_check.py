"""response_check.py — Soll/Ist-Vergleich: setzt der Speicher den Sollwert um? (D-018, D-019)

Der Marstek meldet eine eigene Entladesperre nicht über `dischrg_flag` (Befund 19.10.2026). Die
Integration erkennt deshalb selbst, wenn das Gerät einen bestätigten Sollwert nicht ausführt, und
sperrt die Richtung. Ob ein Adapter diesen Vergleich nutzt, entscheidet er selbst
(`StorageAdapter.response_check_supported`) — wie „lädt/entlädt der Speicher“ ermittelt wird, ist
je Speicher verschieden.

- **Soll** ist der zuletzt bestätigt gesendete Sollwert der HEMS-Anbindung (`last_command`).
- **Ist** liefert das HEMS in `sensor.hems_schnittstelle` (`<prefix>_ladeleistung`,
  `<prefix>_entladeleistung`, HEMS D-069): seine Sensoren sind schneller als die Gerätewerte, mit
  denen der Vergleich springen würde. Fehlt der Istwert, pausiert der Vergleich — es zählt keine
  Fehlzeit, eine bestehende Sperre bleibt.
- Gezählt wird die Zeit, in der der Sollwert mindestens `min_request_w` beträgt und die
  Ist-Leistung derselben Richtung unter `max_actual_w` bleibt — **aufsummiert über mehrere
  Anforderungen**, damit auch Pendeln mit kurzen Anforderungen (18.10.2026: 8–25 s) erkannt wird.
  Liefert das Gerät, fällt die Zeit dieser Richtung auf 0.
- Ab `time_s` ist die Richtung gesperrt, bis der SoC um `RESPONSE_CHECK_RELEASE_SOC_PERCENT` in
  Gegenrichtung gelaufen ist (Entladen: SoC gestiegen, Laden: SoC gefallen); danach wird die
  nächste Anforderung neu geprüft. `time_s` = 0 schaltet den Vergleich ab.

Bewusst ohne Home-Assistant-Import: reine Logik, ohne HA-Instanz testbar.
"""

from __future__ import annotations

import logging

from .const import (
    LOCK_CHARGE_NO_RESPONSE,
    LOCK_DISCHARGE_NO_RESPONSE,
    RESPONSE_CHECK_RELEASE_SOC_PERCENT,
)

_LOGGER = logging.getLogger(__name__)

CHARGE = "charge"
DISCHARGE = "discharge"
_LOCK_REASON = {CHARGE: LOCK_CHARGE_NO_RESPONSE, DISCHARGE: LOCK_DISCHARGE_NO_RESPONSE}
_LABEL = {CHARGE: "Laden", DISCHARGE: "Entladen"}


class ResponseCheck:
    """Soll/Ist-Vergleich je Richtung für einen Speicher (siehe Moduldoc)."""

    def __init__(
        self,
        *,
        name: str,
        time_s: float,
        min_request_w: float,
        max_actual_w: float,
        fallback_step_s: float = 30.0,
    ) -> None:
        self._name = name
        self.time_s = time_s
        self.min_request_w = min_request_w
        self.max_actual_w = max_actual_w
        # Obergrenze je Zählschritt, wenn das HEMS kein Intervall nennt: nach einer Pause zählt
        # die Lücke nicht auf einmal als „keine Reaktion".
        self._fallback_step_s = fallback_step_s
        self.missed_s = {CHARGE: 0.0, DISCHARGE: 0.0}
        self.lock_soc: dict[str, float | None] = {CHARGE: None, DISCHARGE: None}
        self._last_check: float | None = None

    @property
    def enabled(self) -> bool:
        return self.time_s > 0

    def locked(self, direction: str) -> bool:
        return self.lock_soc[direction] is not None

    def lock_reason(self, direction: str) -> str | None:
        return _LOCK_REASON[direction] if self.locked(direction) else None

    def release_soc(self, direction: str) -> float | None:
        """SoC, ab dem die Sperre fällt — für Log und Anzeige."""
        ref = self.lock_soc[direction]
        if ref is None:
            return None
        step = RESPONSE_CHECK_RELEASE_SOC_PERCENT
        return ref + step if direction == DISCHARGE else ref - step

    def update(
        self,
        now: float,
        *,
        requested_w: float,
        charge_w: float | None,
        discharge_w: float | None,
        soc: float | None,
        interval_s: float | None = None,
    ) -> bool:
        """Einen HEMS-Zyklus auswerten. Liefert True, wenn sich eine Sperre geändert hat.

        `requested_w` ist signiert: positiv = entladen, negativ = laden (wie der Passive-Mode).
        `charge_w`/`discharge_w` sind die HEMS-Istwerte; `None` pausiert den Vergleich.
        """
        max_step = 2 * interval_s if interval_s else self._fallback_step_s
        dt = 0.0 if self._last_check is None else min(now - self._last_check, max_step)
        self._last_check = now
        if not self.enabled:
            return False
        changed = self._release(soc)

        if abs(requested_w) < self.min_request_w:
            return changed
        direction = DISCHARGE if requested_w > 0 else CHARGE
        actual = discharge_w if direction == DISCHARGE else charge_w
        if actual is None or self.locked(direction):
            return changed
        if actual >= self.max_actual_w:
            self.missed_s[direction] = 0.0
            return changed
        self.missed_s[direction] += dt
        if self.missed_s[direction] < self.time_s or soc is None:
            return changed
        self.lock_soc[direction] = soc
        self.missed_s[direction] = 0.0
        _LOGGER.warning(
            "%s setzt den Sollwert von %.0f W seit %.0f s nicht um (Ist %.0f W) — %s gesperrt "
            "bis Ladezustand %s %.0f %%.",
            self._name, abs(requested_w), self.time_s, actual, _LABEL[direction],
            "≥" if direction == DISCHARGE else "≤", self.release_soc(direction),
        )
        return True

    def _release(self, soc: float | None) -> bool:
        if soc is None:
            return False  # ohne gültigen SoC bleibt eine Sperre bestehen
        changed = False
        for direction in (DISCHARGE, CHARGE):
            limit = self.release_soc(direction)
            if limit is None:
                continue
            if (direction == DISCHARGE and soc >= limit) or (direction == CHARGE and soc <= limit):
                self.lock_soc[direction] = None
                self.missed_s[direction] = 0.0
                changed = True
                _LOGGER.info(
                    "%s: %s wieder freigegeben (Ladezustand %.0f %%), nächste Anforderung wird "
                    "neu geprüft.",
                    self._name, _LABEL[direction], soc,
                )
        return changed
