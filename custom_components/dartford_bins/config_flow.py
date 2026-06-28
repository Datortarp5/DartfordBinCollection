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

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("uprn", description={"suggested_value": ""}): str,
        vol.Required("postcode", description={"suggested_value": ""}): str,
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
                # Normalise the stored values
                user_input["uprn"] = user_input["uprn"].strip()
                user_input["postcode"] = user_input["postcode"].strip().upper()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={
                "uprn_help": "Find your UPRN at https://www.findmyaddress.co.uk/",
                "postcode_help": "Your full postcode, e.g. DA2 7AL",
            },
        )

    async def async_step_reconfigure(self, user_input: dict | None = None) -> FlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate invalid credentials / no data returned."""
