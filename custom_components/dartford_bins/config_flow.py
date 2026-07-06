"""Config flow for Dartford Bin Collections."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)

from . import fetch_bin_data, DOMAIN

_LOGGER = logging.getLogger(__name__)

REFRESH_OPTIONS = [
    SelectOptionDict(value="6",  label="Every 6 hours"),
    SelectOptionDict(value="12", label="Every 12 hours (recommended)"),
    SelectOptionDict(value="24", label="Every 24 hours"),
    SelectOptionDict(value="48", label="Every 48 hours"),
]


def _build_schema(default_interval: str = "12") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("uprn"): str,
            vol.Required("postcode"): str,
            vol.Required("refresh_interval", default=default_interval): SelectSelector(
                SelectSelectorConfig(
                    options=REFRESH_OPTIONS,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


def _build_options_schema(default_interval: str = "12") -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("refresh_interval", default=default_interval): SelectSelector(
                SelectSelectorConfig(
                    options=REFRESH_OPTIONS,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
    )


async def validate_input(hass: HomeAssistant, data: dict) -> dict:
    """Validate by actually fetching data from council."""
    uprn = data["uprn"].strip()
    postcode = data["postcode"].strip().upper()

    try:
        bins = await hass.async_add_executor_job(fetch_bin_data, uprn, postcode)
    except Exception as err:
        raise CannotConnect(str(err)) from err

    if not bins:
        raise InvalidInput("No bin data returned — check your UPRN and postcode")

    return {"title": f"Dartford Bins ({postcode})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dartford Bin Collections."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidInput:
                errors["base"] = "invalid_input"
            except Exception:
                _LOGGER.exception("Unexpected error during Dartford setup")
                errors["base"] = "unknown"
            else:
                user_input["uprn"] = user_input["uprn"].strip()
                user_input["postcode"] = user_input["postcode"].strip().upper()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow."""
        return DartfordBinsOptionsFlow(config_entry)


class DartfordBinsOptionsFlow(config_entries.OptionsFlow):
    """Options flow — change refresh interval after initial setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = str(
            self._config_entry.options.get(
                "refresh_interval",
                self._config_entry.data.get("refresh_interval", "12"),
            )
        )

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(default_interval=current),
        )


class CannotConnect(HomeAssistantError):
    """Cannot connect to council portal."""

class InvalidInput(HomeAssistantError):
    """Bad UPRN or postcode."""
