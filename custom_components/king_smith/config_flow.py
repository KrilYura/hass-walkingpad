"""Config flow for walkingpad integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult, section
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_CONNECTION_MODE,
    CONF_MAC,
    CONF_NAME,
    CONF_PREFERRED_MODE,
    CONF_REMOTE_CONTROL,
    CONF_REMOTE_CONTROL_ENABLED,
    CONF_STATUS_UPDATE_INTERVAL,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_PREFERRED_MODE,
    DEFAULT_STATUS_UPDATE_SECONDS,
    DOMAIN,
    PREFERRED_MODE_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)

BASE_SCHEMA = {
    vol.Required(CONF_NAME): str,
    vol.Required(CONF_REMOTE_CONTROL): section(
        vol.Schema(
            {
                vol.Required(CONF_REMOTE_CONTROL_ENABLED): bool,
                vol.Required(
                    CONF_PREFERRED_MODE,
                    default=DEFAULT_PREFERRED_MODE,
                ): vol.In(PREFERRED_MODE_OPTIONS),
            }
        ),
        {"collapsed": True},
    ),
}


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): str,
    }
).extend(BASE_SCHEMA)


def _parse_remote_control(user_input: dict[str, Any]) -> dict[str, Any]:
    """Extract remote-control options from a flow form payload."""
    remote_control_data = user_input.get(CONF_REMOTE_CONTROL, {})
    return {
        CONF_REMOTE_CONTROL_ENABLED: remote_control_data.get(
            CONF_REMOTE_CONTROL_ENABLED, False
        ),
        CONF_PREFERRED_MODE: remote_control_data.get(
            CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE
        ),
    }


def _default_entry_options(remote: dict[str, Any]) -> dict[str, Any]:
    """Build the initial options dict for a new config entry."""
    return {
        **remote,
        CONF_CONNECTION_MODE: DEFAULT_CONNECTION_MODE.value,
        CONF_STATUS_UPDATE_INTERVAL: DEFAULT_STATUS_UPDATE_SECONDS,
    }


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input for manual setup.

    The pad may be powered off; only require that a scanner exists and the MAC
    looks usable. Connection happens later when the pad is available.
    """
    if bluetooth.async_scanner_count(hass, connectable=True) < 1:
        raise CannotConnect

    mac = dr.format_mac(data[CONF_MAC])
    return {
        CONF_MAC: mac,
        CONF_NAME: data[CONF_NAME],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for walkingpad."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.discovered_device: dict[str, str] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Return the options flow handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info[CONF_MAC])
                self._abort_if_unique_id_configured()
                remote = _parse_remote_control(user_input)
                return self.async_create_entry(
                    title=info[CONF_NAME],
                    data=info,
                    options=_default_entry_options(remote),
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(dr.format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.discovered_device = {
            "local_name": discovery_info.name,
            "address": discovery_info.address,
        }
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setting up a discovered device."""
        assert self.discovered_device is not None

        if not user_input:
            dev_name = self.discovered_device["local_name"]
            dev_address = self.discovered_device["address"]
            schema_mac = vol.In([f"{dev_name} ({dev_address})"])
            schema = vol.Schema(
                {
                    vol.Required(CONF_MAC): schema_mac,
                }
            ).extend(BASE_SCHEMA)
            return self.async_show_form(step_id="device", data_schema=schema)

        mac = dr.format_mac(self.discovered_device["address"])
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        remote = _parse_remote_control(user_input)
        entry_data = {
            CONF_MAC: mac,
            CONF_NAME: user_input[CONF_NAME],
        }
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=entry_data,
            options=_default_entry_options(remote),
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle an options flow for walkingpad."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            remote = _parse_remote_control(user_input)
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    **remote,
                },
            )

        remote_control_enabled = self.config_entry.options.get(
            CONF_REMOTE_CONTROL_ENABLED, False
        )
        preferred_mode = self.config_entry.options.get(
            CONF_PREFERRED_MODE, DEFAULT_PREFERRED_MODE
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REMOTE_CONTROL): section(
                        vol.Schema(
                            {
                                vol.Required(
                                    CONF_REMOTE_CONTROL_ENABLED,
                                    default=remote_control_enabled,
                                ): bool,
                                vol.Required(
                                    CONF_PREFERRED_MODE,
                                    default=preferred_mode,
                                ): vol.In(PREFERRED_MODE_OPTIONS),
                            }
                        ),
                        {"collapsed": True},
                    ),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
