"""Config flow for Proteus API integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .api import ProteusAPI
from .const import CONF_HOUSEHOLD_ID, CONF_INVERTER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_INVERTER_ID): cv.string,
        vol.Optional(CONF_HOUSEHOLD_ID): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = ProteusAPI(
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        inverter_id=data.get(CONF_INVERTER_ID),
        household_id=data.get(CONF_HOUSEHOLD_ID),
    )

    # Test login
    if not await hass.async_add_executor_job(api.login):
        raise InvalidAuth

    # If IDs not provided, try to auto-detect from user profile
    if not data.get(CONF_INVERTER_ID) or not data.get(CONF_HOUSEHOLD_ID):
        try:
            # Get list of user's inverters
            inverters = await hass.async_add_executor_job(api.get_user_inverters)

            if inverters and len(inverters) > 0:
                # Use first inverter
                first_inverter = inverters[0]
                data[CONF_INVERTER_ID] = first_inverter.get("inverter_id")
                data[CONF_HOUSEHOLD_ID] = first_inverter.get("household_id")

                _LOGGER.info("Auto-detected %d inverter(s), using first one", len(inverters))

                # Update API with detected IDs
                api.inverter_id = data[CONF_INVERTER_ID]
                api.household_id = data[CONF_HOUSEHOLD_ID]
            else:
                _LOGGER.error("No inverters found for this account")
                raise CannotConnect
        except Exception as err:
            _LOGGER.error("Failed to auto-detect inverter IDs: %s", err)
            raise CannotConnect from err

    # Try to get dashboard data to verify IDs
    try:
        await hass.async_add_executor_job(api.get_dashboard_data)
    except Exception as err:
        _LOGGER.error("Failed to get dashboard data: %s", err)
        raise CannotConnect from err

    return {"title": f"Proteus ({data[CONF_EMAIL]})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Proteus."""

    VERSION = 1

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
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""
