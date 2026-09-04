"""switch.py — pausiert/setzt die automatischen Schreibvorgänge der HEMS-Anbindung fort (D-011).

Nur angelegt, wenn für den Entry ein HEMS-Präfix hinterlegt ist — ohne HEMS-Anbindung gäbe es
nichts zu pausieren (`hems_bridge.py` existiert dann gar nicht, siehe `__init__.py`). Ausgeschaltet
lässt sich `number.<prefix>_soll_ladeleistung`/`_soll_entladeleistung` von Hand bedienen, ohne dass
der nächste HEMS-Zyklus den Wert sofort überschreibt (siehe docs/bekannte-luecken.md). Ändert selbst
nie einen Geräte-Sollwert — nur, ob `hems_bridge.py` das tut (Invariante 5, docs/architektur.md).

`entity_category=CONFIG` gruppiert diesen Schalter auf der Geräteseite unter „Konfiguration",
getrennt von den Mess- und Steuer-Entities der übrigen Plattformen.
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HEMS_ENTITY_PREFIX, CONF_MANUFACTURER, DOMAIN, MANUFACTURER_NAMES
from .coordinator import BatteryBridgeConfigEntry, BatteryBridgeCoordinator

_DESCRIPTION = SwitchEntityDescription(
    key="hems_steuerung_aktiv",
    translation_key="hems_steuerung_aktiv",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BatteryBridgeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Den Schalter nur anlegen, wenn dieser Speicher überhaupt eine HEMS-Anbindung hat."""
    if not entry.data.get(CONF_HEMS_ENTITY_PREFIX):
        return
    async_add_entities([BatteryBridgeHemsControlSwitch(entry.runtime_data, entry)])


class BatteryBridgeHemsControlSwitch(CoordinatorEntity[BatteryBridgeCoordinator], SwitchEntity):
    """Pausiert/setzt `hems_bridge.py`s automatische Schreibvorgänge fort."""

    entity_description: SwitchEntityDescription
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
    def is_on(self) -> bool:
        # coordinator.hems_bridge ist an dieser Stelle nie None: diese Entity wird nur angelegt,
        # wenn der Entry ein HEMS-Präfix hat, und __init__.py legt hems_bridge in genau diesem
        # Fall an, bevor die Platforms überhaupt aufgerufen werden.
        return self.coordinator.hems_bridge.enabled

    async def async_turn_on(self, **kwargs: object) -> None:
        await self.coordinator.hems_bridge.async_resume()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: object) -> None:
        await self.coordinator.hems_bridge.async_pause()
        self.async_write_ha_state()
