"""number.py — Soll-Ladeleistung, Soll-Entladeleistung je Speicher-Instanz (Schreibzugriff, M2).

Die Marstek Local API erlaubt kein Zurücklesen des aktuellen Passive-Mode-Sollwerts — die
Entity zeigt deshalb den zuletzt erfolgreich gesendeten Wert, nicht zwingend den tatsächlichen
Gerätezustand (`_attr_assumed_state`). Quellenlage und offene Punkte zum Schreibpfad:
docs/bekannte-luecken.md.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .adapters.base import StorageAdapter, StorageAdapterError
from .const import CONF_MANUFACTURER, DOMAIN, MANUFACTURER_NAMES
from .coordinator import BatteryBridgeConfigEntry, BatteryBridgeCoordinator

# Obergrenze aus der Community-Dokumentation der Marstek Local API (Passive-Mode-Range laut
# jaapp/ha-marstek-local-api: -10000..10000 W gesamt) — keine geräte-spezifisch geprüfte
# Grenze. Die tatsächlich sinnvolle Grenze je Speicher ist Sache der HEMS-Konfiguration
# (available_charge_power_w/available_discharge_power_w), nicht dieser Integration
# (Nicht-Ziel: keine Regel-/Verteilungslogik, siehe docs/architektur.md).
_MAX_POWER_W = 10000


@dataclass(frozen=True, kw_only=True)
class BatteryBridgeNumberDescription(NumberEntityDescription):
    """Beschreibung + die Adapter-Methode, die einen neuen Sollwert tatsächlich sendet."""

    write_fn: Callable[[StorageAdapter, float], Awaitable[None]]


NUMBER_DESCRIPTIONS: tuple[BatteryBridgeNumberDescription, ...] = (
    BatteryBridgeNumberDescription(
        key="soll_ladeleistung",
        translation_key="soll_ladeleistung",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=_MAX_POWER_W,
        native_step=10,
        write_fn=lambda adapter, value: adapter.write_charge_power(value),
    ),
    BatteryBridgeNumberDescription(
        key="soll_entladeleistung",
        translation_key="soll_entladeleistung",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        mode=NumberMode.BOX,
        native_min_value=0,
        native_max_value=_MAX_POWER_W,
        native_step=10,
        write_fn=lambda adapter, value: adapter.write_discharge_power(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Die beiden Soll-Leistungs-Entities für diesen Entry anlegen."""
    coordinator = entry.runtime_data
    async_add_entities(
        BatteryBridgeNumber(coordinator, entry, description)
        for description in NUMBER_DESCRIPTIONS
    )


class BatteryBridgeNumber(CoordinatorEntity[BatteryBridgeCoordinator], NumberEntity):
    """Ein Soll-Leistungswert, der bei jeder Änderung sofort an den Adapter geschrieben wird."""

    entity_description: BatteryBridgeNumberDescription
    _attr_has_entity_name = True
    _attr_assumed_state = True  # Sollwert lässt sich nicht zurücklesen, siehe Moduldoc.

    def __init__(
        self,
        coordinator: BatteryBridgeCoordinator,
        entry: BatteryBridgeConfigEntry,
        description: BatteryBridgeNumberDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.title,
            manufacturer=MANUFACTURER_NAMES.get(
                entry.data[CONF_MANUFACTURER], entry.data[CONF_MANUFACTURER]
            ),
        )
        # Kein Read-Pfad für den aktuellen Sollwert (siehe Moduldoc) — 0 ist der einzige
        # Zustand, den wir ohne einen vorherigen eigenen Schreibvorgang kennen können.
        self._attr_native_value = 0.0

    async def async_set_native_value(self, value: float) -> None:
        """Neuen Sollwert an den Adapter senden — meldet Fehler, statt still zu scheitern."""
        try:
            await self.entity_description.write_fn(self.coordinator.adapter, value)
        except StorageAdapterError as exc:
            raise HomeAssistantError(str(exc)) from exc

        self._attr_native_value = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
