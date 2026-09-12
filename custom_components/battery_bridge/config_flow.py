"""config_flow.py — Hersteller wählen, Verbindungsdaten je Adapter, Verbindungstest."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig

from .adapters.base import StorageAdapterError
from .adapters.marstek_udp import MarstekUdpAdapter
from .const import (
    CONF_DISPLAY_NAME,
    CONF_HEMS_ENTITY_PREFIX,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    MANUFACTURER_MARSTEK,
    MARSTEK_UDP_DEFAULT_PORT,
    MAX_UPDATE_INTERVAL_SECONDS,
    MIN_UPDATE_INTERVAL_SECONDS,
    PROTOCOL_MARSTEK_UDP,
)

_LOGGER = logging.getLogger(__name__)

# Bisher hat jeder Hersteller genau ein Protokoll — der Auswahlschritt entfällt dann
# automatisch (Plan Abschnitt 6). Ein zweites Protokoll für einen bestehenden Hersteller
# (D-006) braucht hier einen echten Auswahlschritt, keine Änderung an diesem Schema.
_MANUFACTURERS = {MANUFACTURER_MARSTEK: "Marstek"}


def _validate_update_interval(user_input: dict[str, Any], errors: dict[str, str]) -> int:
    """Abfrageintervall (Sekunden) aus dem Formular gegen den erlaubten Bereich prüfen.

    Schreibt bei Verstoß einen feldbezogenen Fehler statt vol.Range im Schema zu nutzen —
    ein dort ausgelöstes vol.Invalid würde Home Assistant als generischen Flow-Fehler zeigen,
    nicht als Fehler am betroffenen Feld (siehe data_entry_flow.py).
    """
    update_interval = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS)
    if not (MIN_UPDATE_INTERVAL_SECONDS <= update_interval <= MAX_UPDATE_INTERVAL_SECONDS):
        errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
    return update_interval


class BatteryBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config-Flow: Hersteller wählen, dann Verbindungsdaten des zugehörigen Adapters."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 1: Hersteller wählen."""
        if user_input is not None:
            manufacturer = user_input[CONF_MANUFACTURER]
            if manufacturer == MANUFACTURER_MARSTEK:
                # Marstek hat aktuell nur ein Protokoll — Auswahlschritt entfällt.
                return await self.async_step_marstek_udp()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MANUFACTURER, default=MANUFACTURER_MARSTEK): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=key, label=label)
                                for key, label in _MANUFACTURERS.items()
                            ]
                        )
                    ),
                }
            ),
        )

    async def async_step_marstek_udp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 2 (Marstek/UDP): Verbindungsdaten, Verbindungstest, Entry anlegen."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            update_interval = _validate_update_interval(user_input, errors)

            if not errors:
                await self.async_set_unique_id(f"{host}:{port}")
                self._abort_if_unique_id_configured()

                adapter = MarstekUdpAdapter(host, port)
                try:
                    await adapter.connect()
                    await adapter.read()
                except StorageAdapterError as exc:
                    _LOGGER.debug("Verbindungstest zu %s:%s fehlgeschlagen: %s", host, port, exc)
                    errors["base"] = "cannot_connect"
                else:
                    display_name = user_input.get(CONF_DISPLAY_NAME) or f"Marstek {host}"
                    return self.async_create_entry(
                        title=display_name,
                        data={
                            CONF_MANUFACTURER: MANUFACTURER_MARSTEK,
                            CONF_PROTOCOL: PROTOCOL_MARSTEK_UDP,
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_HEMS_ENTITY_PREFIX: user_input.get(CONF_HEMS_ENTITY_PREFIX)
                            or None,
                        },
                        options={CONF_UPDATE_INTERVAL: update_interval},
                    )
                finally:
                    await adapter.close()

        return self.async_show_form(
            step_id="marstek_udp",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DISPLAY_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=MARSTEK_UDP_DEFAULT_PORT): int,
                    vol.Optional(CONF_HEMS_ENTITY_PREFIX): str,
                    vol.Optional(
                        CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL_SECONDS
                    ): int,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BatteryBridgeOptionsFlowHandler:
        """Options-Flow zum nachträglichen Ändern des Abfrageintervalls (D-014)."""
        return BatteryBridgeOptionsFlowHandler()


class BatteryBridgeOptionsFlowHandler(OptionsFlow):
    """Options-Flow: einziges Feld, das Abfrageintervall in Sekunden."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einzelner Schritt: Abfrageintervall anzeigen/ändern."""
        errors: dict[str, str] = {}

        if user_input is not None:
            update_interval = _validate_update_interval(user_input, errors)
            if not errors:
                return self.async_create_entry(
                    title="", data={CONF_UPDATE_INTERVAL: update_interval}
                )

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_UPDATE_INTERVAL, default=current_interval): int,
                }
            ),
            errors=errors,
        )
