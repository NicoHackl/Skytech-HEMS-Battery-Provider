"""binary_sensor.py — zeigt, ob das SkytechHEMS-Lebenszeichen frisch ist (D-016).

Nur angelegt, wenn für den Entry ein HEMS-Präfix hinterlegt ist. An heißt: das HEMS hat innerhalb
der Frist einen Zyklus veröffentlicht, die Anbindung setzt seinen Sollwert um. Aus heißt: der
Speicher steht mangels Lebenszeichen auf 0 W (siehe `hems_bridge.py`, `heartbeat.py`).
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HEMS_ENTITY_PREFIX, CONF_MANUFACTURER, DOMAIN, MANUFACTURER_NAMES
from .coordinator import BatteryBridgeConfigEntry, BatteryBridgeCoordinator

_DESCRIPTION = BinarySensorEntityDescription(
    key="hems_lebenszeichen",
    translation_key="hems_lebenszeichen",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Den Sensor nur anlegen, wenn dieser Speicher eine HEMS-Anbindung hat."""
    if not entry.data.get(CONF_HEMS_ENTITY_PREFIX):
        return
    async_add_entities([BatteryBridgeHemsHeartbeatSensor(entry.runtime_data, entry)])


class BatteryBridgeHemsHeartbeatSensor(
    CoordinatorEntity[BatteryBridgeCoordinator], BinarySensorEntity
):
    """An, solange das HEMS-Lebenszeichen frisch ist."""

    entity_description: BinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BatteryBridgeCoordinator,
        entry: BatteryBridgeConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = _DESCRIPTION
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{_DESCRIPTION.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.title,
            manufacturer=MANUFACTURER_NAMES.get(
                entry.data[CONF_MANUFACTURER], entry.data[CONF_MANUFACTURER]
            ),
        )

    @property
    def available(self) -> bool:
        # Unabhängig vom Poll: das Lebenszeichen betrifft das HEMS, nicht die Verbindung zum Gerät.
        return True

    @property
    def is_on(self) -> bool:
        # hems_bridge existiert hier immer — Anlage nur mit HEMS-Präfix (siehe switch.py).
        return self.coordinator.hems_bridge.heartbeat_fresh
