"""The FRA Betriebsrichtung integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import FraBetriebsrichtungCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


@dataclass
class FraBetriebsrichtungRuntimeData:
    """Runtime data for FRA Betriebsrichtung."""

    coordinator: FraBetriebsrichtungCoordinator


FraBetriebsrichtungConfigEntry = ConfigEntry[FraBetriebsrichtungRuntimeData]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
) -> bool:
    """Set up FRA Betriebsrichtung from a config entry."""
    coordinator = FraBetriebsrichtungCoordinator(
        hass,
        entry,
        async_get_clientsession(hass),
    )
    # Keep async_refresh here so entities are created as unavailable when
    # both public sources are temporarily unreachable during setup.
    await coordinator.async_refresh()

    entry.runtime_data = FraBetriebsrichtungRuntimeData(coordinator=coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
