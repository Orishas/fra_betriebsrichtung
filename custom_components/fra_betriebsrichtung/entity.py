"""Shared entity helpers for FRA Betriebsrichtung."""

from __future__ import annotations

from typing import Any

from .const import (
    ATTR_ERRORS,
    ATTR_FALLBACK_OK,
    ATTR_FALLBACK_USED,
    ATTR_LAST_SUCCESS,
    ATTR_PRIMARY_OK,
    CONF_NOISE_DIRECTION,
    DEFAULT_NOISE_DIRECTION,
    DOMAIN,
    UMWELTHAUS_URL,
)
from .models import ForecastSlot, FraBetriebsrichtungData


def configured_noise_direction(entry: Any) -> str:
    """Return the configured local noise direction."""
    return entry.options.get(CONF_NOISE_DIRECTION, DEFAULT_NOISE_DIRECTION)


def device_info() -> dict[str, Any]:
    """Return shared device info."""
    return {
        "configuration_url": UMWELTHAUS_URL,
        "identifiers": {(DOMAIN, "frankfurt_airport")},
        "manufacturer": "FRA Betriebsrichtung",
        "name": "Frankfurt Airport",
    }


def health_attributes(
    data: FraBetriebsrichtungData,
    *,
    include_empty_errors: bool = False,
) -> dict[str, Any]:
    """Return source health attributes."""
    errors = list(data.errors)
    return {
        ATTR_PRIMARY_OK: data.primary_ok,
        ATTR_FALLBACK_OK: data.fallback_ok,
        ATTR_FALLBACK_USED: data.fallback_used,
        ATTR_LAST_SUCCESS: data.last_success,
        ATTR_ERRORS: errors if include_empty_errors or errors else None,
    }


def suggested_object_id(key: str) -> str:
    """Return a stable, language-independent entity object id."""
    return f"{DOMAIN}_{key}"


def first_forecast_slot(data: FraBetriebsrichtungData | None) -> ForecastSlot | None:
    """Return the first forecast slot."""
    if data is None or not data.forecast_slots:
        return None
    return data.forecast_slots[0]


def next_noise_slot(
    data: FraBetriebsrichtungData | None,
    noise_direction: str,
) -> ForecastSlot | None:
    """Return the first forecast slot matching the local noise direction."""
    if data is None:
        return None
    return next(
        (
            slot
            for slot in data.forecast_slots
            if slot_matches_direction(slot, noise_direction)
        ),
        None,
    )


def slot_label(slot: ForecastSlot) -> str:
    """Return a short label for a forecast slot."""
    return f"{slot.direction} von {slot.start} bis {slot.end}"


def slot_matches_direction(slot: ForecastSlot, direction: str) -> bool:
    """Return whether a slot includes a direction."""
    return direction in {part.strip() for part in slot.direction.split("/")}


def without_none(values: dict[str, Any]) -> dict[str, Any]:
    """Return a copy without None values."""
    return {key: value for key, value in values.items() if value is not None}
