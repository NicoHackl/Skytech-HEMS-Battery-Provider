"""interface.py — sensor.battery_provider_schnittstelle, die eine Schnittstellen-Entität (D-019).

Grundsatz (Vertrag HEMS ↔ Battery-Provider 2.0): Jede Einheit veröffentlicht genau eine
`sensor.<einheit>_schnittstelle` mit allen Informationen für die anderen Teilnehmer. Für diese
Integration ist das **ein** Sensor über alle Speicher, nicht einer je Speicher:

- State: die `hems_entity_prefix` aller Einträge mit HEMS-Anbindung, durch Komma getrennt.
- Je Speicher `<prefix>_ladefreigabe` / `<prefix>_entladefreigabe` (Bool),
  `<prefix>_ladesperrgrund` / `<prefix>_entladesperrgrund` (Text oder `None`) und bei einer Sperre
  aus dem Soll/Ist-Vergleich `<prefix>_sperre_bis_soc_prozent`.

Weil der Sensor über alle Config-Entries geht, ist er keine Registry-Entität, sondern wird per
`hass.states.async_set` geschrieben — wie SkytechHEMS seine Schnittstelle schreibt. Folge: Er
lässt sich in der Oberfläche nicht umbenennen und steht nach einem HA-Neustart erst wieder, wenn
der erste Eintrag geladen ist.

Freigaben: Ein nicht erreichbarer Speicher ist in beiden Richtungen gesperrt
(`nicht_erreichbar`). Sonst sperren die Gerätemeldung (`StorageState.charge_allowed` /
`discharge_allowed`, `None` heißt frei) und der Soll/Ist-Vergleich der HEMS-Anbindung.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    LOCK_CHARGE_DEVICE,
    LOCK_CHARGE_TIME,
    LOCK_DISCHARGE_DEVICE,
    LOCK_DISCHARGE_TIME,
    LOCK_EMERGENCY_RESERVE,
)
from .response_check import CHARGE, DISCHARGE

if TYPE_CHECKING:
    from .coordinator import BatteryBridgeCoordinator

INTERFACE_ENTITY_ID = "sensor.battery_provider_schnittstelle"
# Version der Attributstruktur (Vertrag HEMS ↔ Battery-Provider 2.0).
INTERFACE_VERSION = 2
LOCK_UNREACHABLE = "nicht_erreichbar"
_DATA_KEY = "interface"

# Gerätesperrgründe aus `StorageState.lock_reasons` je Richtung.
_CHARGE_REASONS = {LOCK_CHARGE_DEVICE, LOCK_CHARGE_TIME}
_DISCHARGE_REASONS = {LOCK_DISCHARGE_DEVICE, LOCK_DISCHARGE_TIME, LOCK_EMERGENCY_RESERVE}


def get_interface(hass: HomeAssistant) -> BatteryProviderInterface:
    """Die eine Instanz je HA-Installation, bei Bedarf angelegt."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if _DATA_KEY not in domain_data:
        domain_data[_DATA_KEY] = BatteryProviderInterface(hass)
    return domain_data[_DATA_KEY]


class BatteryProviderInterface:
    """Sammelt alle Speicher mit HEMS-Anbindung und schreibt den gemeinsamen Sensor."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        # Präfix → Coordinator, in Reihenfolge der Anmeldung (Reihenfolge im State).
        self._members: dict[str, BatteryBridgeCoordinator] = {}
        self._unsubs: dict[str, Callable[[], None]] = {}
        self._last_written: tuple[str, dict[str, Any]] | None = None

    @callback
    def register(self, prefix: str, coordinator: BatteryBridgeCoordinator) -> None:
        """Einen Speicher aufnehmen; jede Coordinator-Aktualisierung schreibt den Sensor neu."""
        self.unregister(prefix)
        self._members[prefix] = coordinator
        self._unsubs[prefix] = coordinator.async_add_listener(self.async_publish)
        self.async_publish()

    @callback
    def unregister(self, prefix: str) -> None:
        """Einen Speicher entfernen (Unload); ohne Speicher verschwindet der Sensor."""
        unsub = self._unsubs.pop(prefix, None)
        if unsub is not None:
            unsub()
        if self._members.pop(prefix, None) is None:
            return
        if self._members:
            self.async_publish()
        else:
            self._hass.states.async_remove(INTERFACE_ENTITY_ID)
            self._last_written = None

    @callback
    def async_publish(self) -> None:
        """State und Attribute neu berechnen; geschrieben wird nur bei einer Änderung."""
        attributes: dict[str, Any] = {
            "friendly_name": "Battery-Provider-Schnittstelle",
            "icon": "mdi:battery-sync",
            "schnittstelle_version": INTERFACE_VERSION,
        }
        for prefix, coordinator in self._members.items():
            attributes.update(_member_attributes(prefix, coordinator))
        state = ",".join(self._members)
        if self._last_written == (state, attributes):
            return
        self._last_written = (state, attributes)
        self._hass.states.async_set(INTERFACE_ENTITY_ID, state, attributes)


def _member_attributes(prefix: str, coordinator: BatteryBridgeCoordinator) -> dict[str, Any]:
    data = coordinator.data
    if not coordinator.last_update_success or data is None or not data.available:
        return {
            f"{prefix}_ladefreigabe": False,
            f"{prefix}_entladefreigabe": False,
            f"{prefix}_ladesperrgrund": LOCK_UNREACHABLE,
            f"{prefix}_entladesperrgrund": LOCK_UNREACHABLE,
        }

    charge_reasons, discharge_reasons = _device_reasons(data.lock_reasons)
    if data.charge_allowed is False and not charge_reasons:
        charge_reasons.append(LOCK_CHARGE_DEVICE)
    if data.discharge_allowed is False and not discharge_reasons:
        discharge_reasons.append(LOCK_DISCHARGE_DEVICE)

    bridge = coordinator.hems_bridge
    check = bridge.response_check if bridge is not None else None
    release_soc = None
    if check is not None:
        for direction, reasons in ((CHARGE, charge_reasons), (DISCHARGE, discharge_reasons)):
            reason = check.lock_reason(direction)
            if reason is not None:
                reasons.append(reason)
                release_soc = check.release_soc(direction)

    attributes: dict[str, Any] = {
        f"{prefix}_ladefreigabe": not charge_reasons,
        f"{prefix}_entladefreigabe": not discharge_reasons,
        f"{prefix}_ladesperrgrund": ", ".join(charge_reasons) or None,
        f"{prefix}_entladesperrgrund": ", ".join(discharge_reasons) or None,
    }
    if release_soc is not None:
        attributes[f"{prefix}_sperre_bis_soc_prozent"] = release_soc
    return attributes


def _device_reasons(lock_reasons: tuple[str, ...]) -> tuple[list[str], list[str]]:
    """Gerätesperrgründe nach Richtung aufteilen."""
    charge = [r for r in lock_reasons if r in _CHARGE_REASONS]
    discharge = [r for r in lock_reasons if r in _DISCHARGE_REASONS]
    return charge, discharge
