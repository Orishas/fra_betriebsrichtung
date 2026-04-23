"""The FRA Betriebsrichtung integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SERVICE_REFRESH
from .coordinator import FraBetriebsrichtungCoordinator
from .entity import (
    configured_noise_direction,
    first_forecast_slot,
    next_direction_change_slot,
    next_noise_slot,
    slot_matches_direction,
)
from .models import FraBetriebsrichtungData

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FraBetriebsrichtungRuntimeData:
    """Runtime data for FRA Betriebsrichtung."""

    coordinator: FraBetriebsrichtungCoordinator


FraBetriebsrichtungConfigEntry = ConfigEntry[FraBetriebsrichtungRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up FRA Betriebsrichtung services."""
    hass.data.setdefault(DOMAIN, {})

    async def handle_refresh(call: ServiceCall) -> dict[str, Any] | None:
        """Handle manual refresh action."""
        return await _async_handle_refresh(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


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
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_handle_refresh(
    hass: HomeAssistant,
    call: ServiceCall,
) -> dict[str, Any] | None:
    """Refresh the single FRA Betriebsrichtung config entry."""
    entry = _loaded_entry(hass)
    return_response = getattr(call, "return_response", False)
    if entry is None:
        raise HomeAssistantError("FRA Betriebsrichtung has no loaded config entry")

    coordinator = entry.runtime_data.coordinator
    try:
        await coordinator.async_request_refresh()
    except Exception as err:  # noqa: BLE001 - action should be automation-friendly
        _LOGGER.debug("Manual refresh failed", exc_info=err)
        raise HomeAssistantError("Failed to refresh FRA Betriebsrichtung") from err

    if return_response:
        return _refresh_response(coordinator.data, configured_noise_direction(entry))
    return None


def _loaded_entry(hass: HomeAssistant) -> FraBetriebsrichtungConfigEntry | None:
    entries = hass.data.get(DOMAIN, {})
    return next(iter(entries.values()), None)


def _refresh_response(
    data: FraBetriebsrichtungData | None,
    noise_direction: str | None,
) -> dict[str, Any]:
    first_slot = first_forecast_slot(data)
    next_noise = (
        next_noise_slot(data, noise_direction) if data and noise_direction else None
    )
    next_change = next_direction_change_slot(data)
    response: dict[str, Any] = {
        "current_direction": data.current_direction if data else None,
        "forecast_direction": first_slot.direction if first_slot else None,
        "noise_active": (
            data.current_direction == noise_direction
            if data and data.current_direction and noise_direction
            else None
        ),
        "forecast_noise_active": (
            slot_matches_direction(first_slot, noise_direction)
            if first_slot and noise_direction
            else None
        ),
        "next_noise_slot": next_noise.as_dict() if next_noise else None,
        "next_direction_change": next_change.as_dict() if next_change else None,
        "source": data.source if data else None,
        "last_update": data.last_update if data else None,
    }
    return response
