"""Diagnostics support for FRA Betriebsrichtung."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import FraBetriebsrichtungConfigEntry
from .const import CONF_NOISE_DIRECTION, DEFAULT_NOISE_DIRECTION, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.coordinator.data
    return {
        "domain": DOMAIN,
        "options": {
            CONF_NOISE_DIRECTION: entry.options.get(
                CONF_NOISE_DIRECTION,
                DEFAULT_NOISE_DIRECTION,
            ),
        },
        "data": None
        if data is None
        else {
            "current_direction": data.current_direction,
            "current_since": data.current_since,
            "current_since_start": data.current_since_start,
            "current_duration_minutes": data.current_duration_minutes,
            "forecast_summary": data.forecast_summary,
            "forecast_slots": [slot.as_dict() for slot in data.forecast_slots],
            "source": data.source,
            "last_update": data.last_update,
            "primary_ok": data.primary_ok,
            "fallback_ok": data.fallback_ok,
            "fallback_used": data.fallback_used,
            "last_success": data.last_success,
            "errors": list(data.errors),
        },
    }
