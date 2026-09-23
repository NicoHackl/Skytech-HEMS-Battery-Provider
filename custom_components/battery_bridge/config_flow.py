"""config_flow.py — Hersteller wählen, Verbindungsdaten je Adapter, Verbindungstest.

Zugangsdaten (E3DC: Benutzer, Passwort, RSCP-Schlüssel) landen im Config-Entry — dem von Home
Assistant vorgesehenen Ort dafür — und nie im Log (D-015).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .adapters.base import StorageAdapterAuthError, StorageAdapterError
from .adapters.e3dc_rscp import E3dcRscpAdapter
from .adapters.marstek_udp import MarstekUdpAdapter
from .const import (
    CONF_DISPLAY_NAME,
    CONF_HEMS_ENTITY_PREFIX,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    CONF_RSCP_KEY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    E3DC_RSCP_DEFAULT_PORT,
    MANUFACTURER_E3DC,
    MANUFACTURER_MARSTEK,
    MANUFACTURER_NAMES,
    MARSTEK_UDP_DEFAULT_PORT,
    MAX_UPDATE_INTERVAL_SECONDS,
    MIN_UPDATE_INTERVAL_SECONDS,
    PROTOCOL_E3DC_RSCP,
    PROTOCOL_MARSTEK_UDP,
)

_LOGGER = logging.getLogger(__name__)

# Maskierte Eingabe für Passwort und RSCP-Schlüssel.
_SECRET_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


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
            # Jeder Hersteller hat bisher genau ein Protokoll — der Protokoll-Auswahlschritt
            # entfällt (Plan Abschnitt 6). Ein zweites Protokoll für einen bestehenden Hersteller
            # (D-006) braucht hier einen echten Auswahlschritt.
            if manufacturer == MANUFACTURER_MARSTEK:
                return await self.async_step_marstek_udp()
            if manufacturer == MANUFACTURER_E3DC:
                return await self.async_step_e3dc_rscp()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MANUFACTURER, default=MANUFACTURER_MARSTEK): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=key, label=label)
                                for key, label in MANUFACTURER_NAMES.items()
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

    async def async_step_e3dc_rscp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 2 (E3DC/RSCP): Zugangsdaten, Verbindungstest, Entry anlegen (D-015)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            update_interval = _validate_update_interval(user_input, errors)

            if not errors:
                adapter = E3dcRscpAdapter(
                    host,
                    port,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_RSCP_KEY],
                )
                try:
                    await adapter.connect()
                    await adapter.read()
                    serial_number = adapter.serial_number
                except StorageAdapterAuthError as exc:
                    _LOGGER.debug("E3DC %s lehnt die Zugangsdaten ab: %s", host, exc)
                    errors["base"] = "invalid_auth"
                except StorageAdapterError as exc:
                    _LOGGER.debug("Verbindungstest zu E3DC %s fehlgeschlagen: %s", host, exc)
                    errors["base"] = "cannot_connect"
                finally:
                    await adapter.close()

                if not errors:
                    # Seriennummer statt Adresse: bleibt gleich, wenn das Gerät eine neue IP
                    # bekommt. Nur falls das Gerät keine meldet, ersatzweise die Adresse.
                    await self.async_set_unique_id(f"e3dc_{serial_number or f'{host}:{port}'}")
                    self._abort_if_unique_id_configured()
                    display_name = user_input.get(CONF_DISPLAY_NAME) or f"E3DC {host}"
                    return self.async_create_entry(
                        title=display_name,
                        data={
                            CONF_MANUFACTURER: MANUFACTURER_E3DC,
                            CONF_PROTOCOL: PROTOCOL_E3DC_RSCP,
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_RSCP_KEY: user_input[CONF_RSCP_KEY],
                            CONF_HEMS_ENTITY_PREFIX: user_input.get(CONF_HEMS_ENTITY_PREFIX)
                            or None,
                        },
                        options={CONF_UPDATE_INTERVAL: update_interval},
                    )

        return self.async_show_form(
            step_id="e3dc_rscp",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_DISPLAY_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=E3DC_RSCP_DEFAULT_PORT): int,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): _SECRET_SELECTOR,
                    vol.Required(CONF_RSCP_KEY): _SECRET_SELECTOR,
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
