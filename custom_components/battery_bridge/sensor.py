"""sensor.py — SoC, Ist-/HEMS-Soll-Ladeleistung, Ist-/HEMS-Soll-Entladeleistung je Speicher."""

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

from .const import CONF_HEMS_ENTITY_PREFIX, CONF_MANUFACTURER, DOMAIN, MANUFACTURER_NAMES
from .coordinator import BatteryBridgeConfigEntry, BatteryBridgeCoordinator
from .hems_bridge import HemsCommandState
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


@dataclass(frozen=True, kw_only=True)
class BatteryBridgeHemsSensorDescription(SensorEntityDescription):
    """Wie `BatteryBridgeSensorDescription`, aber Quelle ist `HemsCommandState`, nicht
    `StorageState` — der Wert kommt von der HEMS-Anbindung, nicht vom Adapter-Poll."""

    value_fn: Callable[[HemsCommandState], float | None]


HEMS_SENSOR_DESCRIPTIONS: tuple[BatteryBridgeHemsSensorDescription, ...] = (
    BatteryBridgeHemsSensorDescription(
        key="hems_soll_ladeleistung",
        translation_key="hems_soll_ladeleistung",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda command: command.charge_power_w,
    ),
    BatteryBridgeHemsSensorDescription(
        key="hems_soll_entladeleistung",
        translation_key="hems_soll_entladeleistung",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda command: command.discharge_power_w,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Die Lese-Sensoren für diesen Entry anlegen — die beiden HEMS-Sollwert-Sensoren nur, wenn
    für diesen Speicher überhaupt eine HEMS-Anbindung eingerichtet ist (sonst gäbe es nie einen
    Wert dafür, siehe `hems_bridge.py`)."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        BatteryBridgeSensor(coordinator, entry, description) for description in SENSOR_DESCRIPTIONS
    ]
    if entry.data.get(CONF_HEMS_ENTITY_PREFIX):
        entities.extend(
            BatteryBridgeHemsCommandSensor(coordinator, entry, description)
            for description in HEMS_SENSOR_DESCRIPTIONS
        )
    async_add_entities(entities)


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


class BatteryBridgeHemsCommandSensor(CoordinatorEntity[BatteryBridgeCoordinator], SensorEntity):
    """Zeigt den Sollwert, den die HEMS-Anbindung zuletzt erfolgreich an den Adapter gesendet
    hat — schließt die in docs/bekannte-luecken.md dokumentierte Lücke, dass
    `number.<prefix>_soll_*` das nicht abbildet, weil `hems_bridge.py` am Adapter vorbeischreibt.
    """

    entity_description: BatteryBridgeHemsSensorDescription
    _attr_has_entity_name = True
    _attr_assumed_state = True  # kein Read-Pfad zurück zum Gerät, siehe number.py.

    def __init__(
        self,
        coordinator: BatteryBridgeCoordinator,
        entry: BatteryBridgeConfigEntry,
        description: BatteryBridgeHemsSensorDescription,
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
        # Bewusst unabhängig vom Poll-Erfolg des Coordinators (super().available/data.available):
        # ein Lesefehler vom Gerät soll den zuletzt gesendeten HEMS-Sollwert nicht verschwinden
        # lassen. Erst verfügbar, sobald die HEMS-Anbindung mindestens einmal erfolgreich
        # geschrieben hat.
        return self.coordinator.hems_bridge is not None and (
            self.coordinator.hems_bridge.last_command is not None
        )

    @property
    def native_value(self) -> float | None:
        hems_bridge = self.coordinator.hems_bridge
        last_command = hems_bridge.last_command if hems_bridge else None
        if last_command is None:
            return None
        return self.entity_description.value_fn(last_command)
