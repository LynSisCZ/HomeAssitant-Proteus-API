"""The Proteus API integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ProteusAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
]

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Proteus from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Vytvoř API klienta pro autentizaci
    api = ProteusAPI(
        email=entry.data["email"],
        password=entry.data["password"],
        inverter_id=entry.data.get("inverter_id"),
        household_id=entry.data.get("household_id"),
    )

    # Přihlásit se
    try:
        await hass.async_add_executor_job(api.login)
    except Exception as err:
        _LOGGER.error("Failed to login to Proteus: %s", err)
        return False

    # Pokud nejsou zadány IDs, zjisti všechny invertory
    if not entry.data.get("inverter_id") or not entry.data.get("household_id"):
        _LOGGER.info("No inverter_id specified, discovering all inverters...")
        inverters = await hass.async_add_executor_job(api.get_user_inverters)

        if not inverters:
            _LOGGER.error("No inverters found for this account")
            return False

        _LOGGER.info("Found %d inverters, using first one: %s", len(inverters), inverters[0])

        # Použij první inverter
        api.inverter_id = inverters[0]["inverter_id"]
        api.household_id = inverters[0]["household_id"]

        # TODO: V budoucnu můžeme vytvořit config entry pro každý inverter
        # Pro nyní použijeme jen první

    # Vytvoř coordinator pro automatické updaty
    coordinator = ProteusDataUpdateCoordinator(hass, api)

    # Načti první data
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup na jednotlivé platformy
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ProteusDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Proteus data."""

    def __init__(self, hass: HomeAssistant, api: ProteusAPI) -> None:
        """Initialize."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            # Získej všechna data najednou pomocí batch API
            data = await self.hass.async_add_executor_job(
                self.api.get_dashboard_data
            )
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
