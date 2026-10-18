"""sensor.py — SoC, Ist-/HEMS-Soll-Ladeleistung, Ist-/HEMS-Soll-Entladeleistung je Speicher,
dazu der Schnittstellen-Sensor zum HEMS (D-017)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

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

# Version der Attributstruktur des Schnittstellen-Sensors (Vertrag HEMS ↔ Battery-Provider 1.2).
# Steigt nur bei einer inkompatiblen Änderung; neue Attribute kommen additiv dazu.
INTERFACE_VERSION = 1

# Betriebszustand des Schnittstellen-Sensors — stabile Werte, Teil des Vertrags. Angezeigt werden
# die Übersetzungen aus strings.json, nie diese Schlüssel.
INTERFACE_READY = "bereit"
INTERFACE_CHARGE_LOCKED = "laden_gesperrt"
INTERFACE_DISCHARGE_LOCKED = "entladen_gesperrt"
INTERFACE_LOCKED = "gesperrt"
INTERFACE_DISCONNECTED = "getrennt"
INTERFACE_STATES = [
    INTERFACE_READY,
    INTERFACE_CHARGE_LOCKED,
    INTERFACE_DISCHARGE_LOCKED,
    INTERFACE_LOCKED,
    INTERFACE_DISCONNECTED,
]

# Zeitzone für die Anzeige von `gemessen_am` (eiserne Regel 9) — Rechenvorschrift, kein Anzeigetext.
_DISPLAY_TZ = ZoneInfo("Europe/Berlin")


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
        entities.append(BatteryBridgeHemsInterfaceSensor(coordinator, entry))
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
        #
        # Ein *Schreib*fehler wiegt anders als ein Lesefehler: dann ist unbekannt, ob der zuletzt
        # gesendete Sollwert am Gerät überhaupt noch gilt. Der Wert verschwindet deshalb, statt
        # einen unbestätigten Stand vorzutäuschen (siehe hems_bridge.py, `write_ok`).
        hems_bridge = self.coordinator.hems_bridge
        return (
            hems_bridge is not None
            and hems_bridge.last_command is not None
            and hems_bridge.write_ok
        )

    @property
    def native_value(self) -> float | None:
        hems_bridge = self.coordinator.hems_bridge
        last_command = hems_bridge.last_command if hems_bridge else None
        if last_command is None:
            return None
        return self.entity_description.value_fn(last_command)


_INTERFACE_DESCRIPTION = SensorEntityDescription(
    key="hems_schnittstelle",
    translation_key="hems_schnittstelle",
    device_class=SensorDeviceClass.ENUM,
    options=INTERFACE_STATES,
)


class BatteryBridgeHemsInterfaceSensor(CoordinatorEntity[BatteryBridgeCoordinator], SensorEntity):
    """Alles, was zwischen HEMS und Provider fließt, an einer Stelle (D-017, Vertrag 1.2).

    State ist der Betriebszustand des Speichers aus Sicht des HEMS. Die Attribute tragen die
    Messwerte und Gerätefreigaben (Provider → HEMS) und spiegeln, was die Anbindung aus den
    HEMS-Helfern gelesen und an das Gerät gesendet hat (HEMS → Provider). Das HEMS liest SoC,
    Ist-Leistung und Freigaben direkt aus diesen Attributen.
    """

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True
    # Schnell wechselnde Werte nicht in den Recorder: jede Attributänderung schriebe sonst den
    # gesamten Attributsatz neu. Ihr Verlauf steht in den Einzel-Sensoren (Ist-/Soll-Leistung).
    _unrecorded_attributes = frozenset(
        {
            "ist_ladeleistung_w",
            "ist_entladeleistung_w",
            "hems_anforderung_w",
            "gesendet_ladeleistung_w",
            "gesendet_entladeleistung_w",
            "gemessen_am",
        }
    )

    def __init__(
        self,
        coordinator: BatteryBridgeCoordinator,
        entry: BatteryBridgeConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = _INTERFACE_DESCRIPTION
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{_INTERFACE_DESCRIPTION.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.title,
            manufacturer=MANUFACTURER_NAMES.get(
                entry.data[CONF_MANUFACTURER], entry.data[CONF_MANUFACTURER]
            ),
        )

    @property
    def available(self) -> bool:
        # Immer verfügbar: gerade der Ausfall der Geräteverbindung soll als `getrennt` sichtbar
        # sein und vom HEMS gelesen werden, statt als `unavailable` zu verschwinden.
        return True

    def _measurement(self) -> StorageState | None:
        """Der zuletzt gelesene Zustand — `None`, wenn der letzte Poll gescheitert ist."""
        data = self.coordinator.data
        if not self.coordinator.last_update_success or data is None or not data.available:
            return None
        return data

    @property
    def native_value(self) -> str:
        state = self._measurement()
        if state is None:
            return INTERFACE_DISCONNECTED
        charge_locked = state.charge_allowed is False
        discharge_locked = state.discharge_allowed is False
        if charge_locked and discharge_locked:
            return INTERFACE_LOCKED
        if charge_locked:
            return INTERFACE_CHARGE_LOCKED
        if discharge_locked:
            return INTERFACE_DISCHARGE_LOCKED
        return INTERFACE_READY

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self._measurement()
        bridge = self.coordinator.hems_bridge
        command = bridge.last_command if bridge is not None else None
        request = bridge.request if bridge is not None else None
        return {
            "schnittstelle_version": INTERFACE_VERSION,
            "messung_ok": state is not None,
            "gemessen_am": (
                state.last_update.astimezone(_DISPLAY_TZ).strftime("%d.%m.%Y %H:%M:%S")
                if state is not None
                else None
            ),
            "soc_prozent": state.soc_percent if state else None,
            "ist_ladeleistung_w": state.charge_power_w if state else None,
            "ist_entladeleistung_w": state.discharge_power_w if state else None,
            "laden_freigegeben": state.charge_allowed if state else None,
            "entladen_freigegeben": state.discharge_allowed if state else None,
            "sperrgruende": list(state.lock_reasons) if state else [],
            "batterietemperatur_c": state.temperature_c if state else None,
            "nennkapazitaet_wh": state.rated_capacity_wh if state else None,
            "geraet_status_roh": state.raw_status if state else None,
            "hems_anforderung_w": request.power_w if request else None,
            "hems_anforderung_betriebsart": request.mode if request else None,
            "gesendet_ladeleistung_w": (
                command.charge_power_w if command and bridge.write_ok else None
            ),
            "gesendet_entladeleistung_w": (
                command.discharge_power_w if command and bridge.write_ok else None
            ),
            "senden_ok": bridge.write_ok if bridge is not None else None,
            "hems_lebenszeichen": bridge.heartbeat_fresh if bridge is not None else None,
            "hems_steuerung_aktiv": bridge.enabled if bridge is not None else None,
        }
