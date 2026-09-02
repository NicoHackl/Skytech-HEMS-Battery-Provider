"""sensor.py — SoC, Ist-Ladeleistung, Ist-Entladeleistung je Speicher-Instanz."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MANUFACTURER, DOMAIN, MANUFACTURER_NAMES
from .coordinator import BatteryBridgeConfigEntry, BatteryBridgeCoordinator
from .models import StorageState


@dataclass(frozen=True, kw_only=True)
class BatteryBridgeSensorDescription(SensorEntityDescription):
    """Beschreibung + Zugriffsfunktion, damit hier keine drei Klassen dupliziert werden."""

    value_fn: Callable[[StorageState], float | None]


SENSOR_DESCRIPTIONS: tuple[BatteryBridgeSensorDescription, ...] = (
    BatteryBridgeSensorDescription(
        key="soc",
        translation_key="soc",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.soc_percent,
    ),
    BatteryBridgeSensorDescription(
        key="ist_ladeleistung",
        translation_key="ist_ladeleistung",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.charge_power_w,
    ),
    BatteryBridgeSensorDescription(
        key="ist_entladeleistung",
        translation_key="ist_entladeleistung",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.discharge_power_w,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Die drei Lese-Sensoren für diesen Entry anlegen."""
    coordinator = entry.runtime_data
    async_add_entities(
        BatteryBridgeSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class BatteryBridgeSensor(CoordinatorEntity[BatteryBridgeCoordinator], SensorEntity):
    """Ein Messwert eines Speichers, aus dem zuletzt vom Coordinator gelesenen `StorageState`."""

    entity_description: BatteryBridgeSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BatteryBridgeCoordinator,
        entry: BatteryBridgeConfigEntry,
        description: BatteryBridgeSensorDescription,
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

    @property
    def available(self) -> bool:
        # Zusätzlich zur Coordinator-eigenen Verfügbarkeit (letzter Poll erfolgreich) prüfen,
        # ob der Adapter selbst einen gültigen Zustand gemeldet hat (StorageState.available).
        return super().available and self.coordinator.data.available

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator.data)
