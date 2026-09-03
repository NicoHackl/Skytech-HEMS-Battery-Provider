"""hems_bridge.py — optionale, eingebaute Übersetzung der SkytechHEMS-Anforderungshelfer.

Ist für einen Config-Entry ein HEMS-Geräte-Präfix hinterlegt (`config_flow.py`,
`CONF_HEMS_ENTITY_PREFIX`), übernimmt diese Integration selbst die laufende Übersetzung von
HEMS' Anforderungsvertrag — `input_number.ems_<prefix>_anforderung_leistung_w` (signiert,
positiv = laden) und `input_select.ems_<prefix>_anforderung_betriebsart`
(`laden`/`entladen`/`standby`) — in die eigenen Adapter-Schreibaufrufe. Ohne HEMS-Präfix ändert
sich nichts: die Integration bleibt ein reiner Entity-Lieferant (D-009).

Wichtig: `write_charge_power()`/`write_discharge_power()` sind bei der Marstek-UDP-Anbindung kein
additives Zwei-Kanal-Signal, sondern steuern denselben einzigen Passive-Mode-Sollwert — der
zuletzt gesendete Aufruf gewinnt vollständig (siehe `adapters/marstek_udp.py`). Genau deshalb
wird die inaktive Richtung nur beim tatsächlichen Wechsel der Betriebsart einmal auf 0 gesetzt,
nie bei jedem Sync: Bei unverändertem Modus liefe sonst jede reine Leistungsanpassung über zwei
Befehle auf **dasselbe** Feld — erst 0, dann der neue Wert — und am Speicher käme das als
kurzzeitiger Sprung auf 0 W an, obwohl nur der Betrag der bestehenden Richtung sich geändert hat
(siehe `docs/bekannte-luecken.md`, Abschnitt „Speicher springt"). Details und Begründung zur
HEMS-Anbindung insgesamt: docs/adr/D-009-hems-anbindung-in-integration.md.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .adapters.base import StorageAdapterError

if TYPE_CHECKING:
    from .coordinator import BatteryBridgeCoordinator

_LOGGER = logging.getLogger(__name__)

# HEMS' eigene, feste Betriebsart-Werte (docs/device_classes/battery.md im HEMS-Repo) — alles
# andere (inkl. "standby", "unknown", "unavailable") wird wie "standby" behandelt: sicherer Fall,
# nicht raten, was ein unerwarteter Wert bedeuten könnte.
_MODE_LADEN = "laden"
_MODE_ENTLADEN = "entladen"


class HemsBridge:
    """Beobachtet die HEMS-Anforderungshelfer eines Präfixes, übersetzt sie live in Sollwerte."""

    def __init__(self, coordinator: BatteryBridgeCoordinator, hems_entity_prefix: str) -> None:
        self._coordinator = coordinator
        self._hass: HomeAssistant = coordinator.hass
        self._prefix = hems_entity_prefix
        self._power_entity_id = f"input_number.ems_{hems_entity_prefix}_anforderung_leistung_w"
        self._mode_entity_id = f"input_select.ems_{hems_entity_prefix}_anforderung_betriebsart"
        self._unsub: Callable[[], None] | None = None
        self._warned_missing = False
        # Zuletzt erfolgreich angewendete Betriebsart — nur bei einem Wechsel gegenüber diesem
        # Wert wird die inaktive Richtung auf 0 gesetzt (siehe Moduldoc). `None` vor dem ersten
        # erfolgreichen Sync erzwingt beim allerersten Durchlauf immer den Zero-Schritt, auch
        # wenn die Zielrichtung zufällig schon beim vorherigen Geräte-Neustart aktiv war.
        self._last_applied_mode: str | None = None

    async def async_setup(self) -> None:
        """Auf beide HEMS-Helfer hören und den aktuell gesetzten Wert einmal übernehmen."""
        self._unsub = async_track_state_change_event(
            self._hass,
            [self._power_entity_id, self._mode_entity_id],
            self._async_handle_event,
        )
        await self._async_sync()

    def async_unload(self) -> None:
        """Listener entfernen — Gegenstück zu `async_setup()`."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _async_handle_event(self, _event: Event) -> None:
        await self._async_sync()

    async def _async_sync(self) -> None:
        """Aktuelle HEMS-Anforderung lesen und als Sollwert(e) an den Adapter senden."""
        mode_state = self._hass.states.get(self._mode_entity_id)
        power_state = self._hass.states.get(self._power_entity_id)

        if mode_state is None or power_state is None:
            if not self._warned_missing:
                _LOGGER.warning(
                    "HEMS-Helfer für Präfix '%s' nicht gefunden (%s, %s) — HEMS-Anbindung "
                    "bleibt inaktiv, bis SkytechHEMS dieses Gerät angelegt hat.",
                    self._prefix,
                    self._mode_entity_id,
                    self._power_entity_id,
                )
                self._warned_missing = True
            return
        self._warned_missing = False

        leistung_w = _parse_leistung(power_state.state)
        adapter = self._coordinator.adapter
        mode = mode_state.state
        # Nur bei einem tatsächlichen Wechsel der Betriebsart gegenüber dem letzten erfolgreichen
        # Sync die inaktive Richtung zurücksetzen — sonst sendet jede reine Leistungsanpassung
        # bei unveränderter Richtung einen unnötigen Zero-Befehl auf dasselbe Passive-Mode-Feld
        # (siehe Moduldoc). Bei HEMS-Anforderungen, die sich mehrmals pro Sekunde ändern, macht
        # genau das den Unterschied zwischen einer sanften Anpassung und einem sichtbaren Sprung
        # am Speicher.
        mode_changed = mode != self._last_applied_mode

        try:
            if mode == _MODE_LADEN:
                if mode_changed:
                    await adapter.write_discharge_power(0)
                await adapter.write_charge_power(leistung_w)
            elif mode == _MODE_ENTLADEN:
                if mode_changed:
                    await adapter.write_charge_power(0)
                await adapter.write_discharge_power(leistung_w)
            else:
                # "standby" und jeder unerwartete Wert: sicherer Fall, beide Richtungen auf 0.
                await adapter.write_charge_power(0)
                await adapter.write_discharge_power(0)
        except StorageAdapterError as exc:
            _LOGGER.error(
                "HEMS-Anbindung (%s) konnte den Sollwert nicht setzen: %s", self._prefix, exc
            )
            return

        self._last_applied_mode = mode
        await self._coordinator.async_request_refresh()


def _parse_leistung(raw_state: str) -> float:
    """Signierten HEMS-Anforderungswert in einen Betrag (≥ 0) wandeln.

    Fehlend oder nicht-numerisch (`unknown`, `unavailable`, …) wird `0` — derselbe sichere Fall
    wie bei einem unerwarteten Betriebsart-Wert, nicht raten, was gemeint sein könnte.
    """
    try:
        return abs(float(raw_state))
    except (TypeError, ValueError):
        return 0.0
