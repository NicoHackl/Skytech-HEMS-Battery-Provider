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
    CONF_HEMS_TIMEOUT_FACTOR,
    CONF_MANUFACTURER,
    CONF_PROTOCOL,
    CONF_RESPONSE_CHECK_MAX_ACTUAL,
    CONF_RESPONSE_CHECK_MIN_REQUEST,
    CONF_RESPONSE_CHECK_TIME,
    CONF_RSCP_KEY,
    CONF_UPDATE_INTERVAL,
    DEFAULT_RESPONSE_CHECK_MAX_ACTUAL_W,
    DEFAULT_RESPONSE_CHECK_MIN_REQUEST_W,
    DEFAULT_RESPONSE_CHECK_TIME_SECONDS,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
    E3DC_RSCP_DEFAULT_PORT,
    MANUFACTURER_E3DC,
    MANUFACTURER_MARSTEK,
    MANUFACTURER_NAMES,
    MARSTEK_UDP_DEFAULT_PORT,
    MAX_RESPONSE_CHECK_MAX_ACTUAL_W,
    MAX_RESPONSE_CHECK_MIN_REQUEST_W,
    MAX_RESPONSE_CHECK_TIME_SECONDS,
    MAX_UPDATE_INTERVAL_SECONDS,
    MIN_RESPONSE_CHECK_MAX_ACTUAL_W,
    MIN_RESPONSE_CHECK_MIN_REQUEST_W,
    MIN_RESPONSE_CHECK_TIME_SECONDS,
    MIN_UPDATE_INTERVAL_SECONDS,
    PROTOCOL_E3DC_RSCP,
    PROTOCOL_MARSTEK_UDP,
)
from .heartbeat import DEFAULT_TIMEOUT_FACTOR, MAX_TIMEOUT_FACTOR, MIN_TIMEOUT_FACTOR

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


# Soll/Ist-Vergleich (D-018): Feld, Default, Grenzen. Nur beim Marstek im Options-Flow.
_RESPONSE_CHECK_FIELDS: tuple[tuple[str, int, int, int], ...] = (
    (
        CONF_RESPONSE_CHECK_TIME,
        DEFAULT_RESPONSE_CHECK_TIME_SECONDS,
        MIN_RESPONSE_CHECK_TIME_SECONDS,
        MAX_RESPONSE_CHECK_TIME_SECONDS,
    ),
    (
        CONF_RESPONSE_CHECK_MIN_REQUEST,
        DEFAULT_RESPONSE_CHECK_MIN_REQUEST_W,
        MIN_RESPONSE_CHECK_MIN_REQUEST_W,
        MAX_RESPONSE_CHECK_MIN_REQUEST_W,
    ),
    (
        CONF_RESPONSE_CHECK_MAX_ACTUAL,
        DEFAULT_RESPONSE_CHECK_MAX_ACTUAL_W,
        MIN_RESPONSE_CHECK_MAX_ACTUAL_W,
        MAX_RESPONSE_CHECK_MAX_ACTUAL_W,
    ),
)


def _validate_response_check(
    user_input: dict[str, Any], errors: dict[str, str]
) -> dict[str, int]:
    """Werte des Soll/Ist-Vergleichs prüfen — feldbezogen, wie `_validate_update_interval`.

    Die Erkennungszeit darf zusätzlich `0` sein (Vergleich aus). Die Ist-Grenze muss unter der
    Mindest-Anforderung liegen, sonst gälte jede Anforderung sofort als nicht umgesetzt.
    """
    values: dict[str, int] = {}
    for key, default, minimum, maximum in _RESPONSE_CHECK_FIELDS:
        value = user_input.get(key, default)
        allowed_zero = key == CONF_RESPONSE_CHECK_TIME and value == 0
        if not allowed_zero and not (minimum <= value <= maximum):
            errors[key] = f"invalid_{key}"
        values[key] = value
    if (
        CONF_RESPONSE_CHECK_MAX_ACTUAL not in errors
        and CONF_RESPONSE_CHECK_MIN_REQUEST not in errors
        and values[CONF_RESPONSE_CHECK_MAX_ACTUAL] >= values[CONF_RESPONSE_CHECK_MIN_REQUEST]
    ):
        errors[CONF_RESPONSE_CHECK_MAX_ACTUAL] = "response_check_actual_above_request"
    return values


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
    """Options-Flow: Abfrageintervall, mit HEMS-Anbindung zusätzlich der Frist-Faktor (D-016),
    beim Marstek zusätzlich der Soll/Ist-Vergleich (D-018)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einzelner Schritt: Abfrageintervall und ggf. Frist-Faktor anzeigen/ändern."""
        errors: dict[str, str] = {}
        has_hems = bool(self.config_entry.data.get(CONF_HEMS_ENTITY_PREFIX))
        is_marstek = self.config_entry.data.get(CONF_MANUFACTURER) == MANUFACTURER_MARSTEK

        if user_input is not None:
            update_interval = _validate_update_interval(user_input, errors)
            data: dict[str, Any] = {CONF_UPDATE_INTERVAL: update_interval}
            if has_hems:
                factor = user_input.get(CONF_HEMS_TIMEOUT_FACTOR, DEFAULT_TIMEOUT_FACTOR)
                if not (MIN_TIMEOUT_FACTOR <= factor <= MAX_TIMEOUT_FACTOR):
                    errors[CONF_HEMS_TIMEOUT_FACTOR] = "invalid_hems_timeout_factor"
                data[CONF_HEMS_TIMEOUT_FACTOR] = factor
            if is_marstek:
                data.update(_validate_response_check(user_input, errors))
            if not errors:
                return self.async_create_entry(title="", data=data)

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS
        )
        schema: dict[Any, Any] = {
            vol.Optional(CONF_UPDATE_INTERVAL, default=current_interval): int,
        }
        if has_hems:
            current_factor = self.config_entry.options.get(
                CONF_HEMS_TIMEOUT_FACTOR, DEFAULT_TIMEOUT_FACTOR
            )
            schema[vol.Optional(CONF_HEMS_TIMEOUT_FACTOR, default=current_factor)] = int
        if is_marstek:
            for key, default, _minimum, _maximum in _RESPONSE_CHECK_FIELDS:
                current = self.config_entry.options.get(key, default)
                schema[vol.Optional(key, default=current)] = int
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
