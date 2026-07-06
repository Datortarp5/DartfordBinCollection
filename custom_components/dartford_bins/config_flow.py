"""Config flow for Dartford Bin Collections."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from . import fetch_bin_data, DOMAIN

_LOGGER = logging.getLogger(__name__)

REFRESH_OPTIONS = {
    6:  "Every 6 hours",
    12: "Every 12 hours (recommended)",
    24: "Every 24 hours",
    48: "Every 48 hours",
}

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("uprn", description={"suggested_value": "10000000000"}): str,
        vol.Required("postcode", description={"suggested_value": "DA1 1AA"}): str,
        vol.Required("refresh_interval", default=12): vol.In(REFRESH_OPTIONS),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required("refresh_interval", default=12): vol.In(REFRESH_OPTIONS),
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate the user input by actually fetching data."""
    uprn = data["uprn"].strip()
    postcode = data["postcode"].strip().upper()

    try:
        bins = await hass.async_add_executor_job(fetch_bin_data, uprn, postcode)
    except Exception as err:
        raise CannotConnect(str(err)) from err

    if not bins:
        raise InvalidAuth("No bin data returned — check your UPRN and postcode")

    return {"title": f"Dartford Bins ({postcode})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dartford Bin Collections."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during Dartford config validation")
                errors["base"] = "unknown"
            else:
                user_input["uprn"] = user_input["uprn"].strip()
                user_input["postcode"] = user_input["postcode"].strip().upper()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "uprn_help": "Find your UPRN at https://www.findmyaddress.co.uk/",
                "postcode_help": "Your full Dartford postcode, e.g. DA1 1AA",
            },
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return DartfordBinsOptionsFlow(config_entry)

    async def async_step_reconfigure(self, user_input: dict | None = None) -> FlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user(user_input)


class DartfordBinsOptionsFlow(config_entries.OptionsFlow):
    """Handle options — lets user change refresh interval after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            "refresh_interval",
            self._config_entry.data.get("refresh_interval", 12)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("refresh_interval", default=current_interval): vol.In(REFRESH_OPTIONS),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid credentials / no data returned."""
