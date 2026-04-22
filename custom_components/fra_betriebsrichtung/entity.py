"""Shared entity helpers for FRA Betriebsrichtung."""

from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Any

from .const import (
    ATTR_ERRORS,
    ATTR_FALLBACK_OK,
    ATTR_FALLBACK_USED,
    ATTR_LAST_SUCCESS,
    ATTR_PRIMARY_OK,
    CONF_NOISE_DIRECTION,
    CONF_WARNING_MINUTES,
    DEFAULT_NOISE_DIRECTION,
    DEFAULT_WARNING_MINUTES,
    DOMAIN,
    UMWELTHAUS_URL,
)
from .models import ForecastSlot, FraBetriebsrichtungData


def configured_noise_direction(entry: Any) -> str:
    """Return the configured local noise direction."""
    return entry.options.get(CONF_NOISE_DIRECTION, DEFAULT_NOISE_DIRECTION)


def configured_warning_minutes(entry: Any) -> int:
    """Return the configured warning window in minutes."""
    return int(entry.options.get(CONF_WARNING_MINUTES, DEFAULT_WARNING_MINUTES))


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


def next_direction_change_slot(
    data: FraBetriebsrichtungData | None,
) -> ForecastSlot | None:
    """Return the first forecast slot that differs from the current direction."""
    if data is None or data.current_direction is None:
        return None
    return next(
        (
            slot
            for slot in data.forecast_slots
            if not slot_matches_direction(slot, data.current_direction)
        ),
        None,
    )


def next_upcoming_noise_slot(
    data: FraBetriebsrichtungData | None,
    noise_direction: str,
    now: datetime,
) -> ForecastSlot | None:
    """Return the first future noise slot."""
    if data is None:
        return None
    return next(
        (
            slot
            for slot in data.forecast_slots
            if slot_matches_direction(slot, noise_direction)
            and _is_upcoming(slot, now)
        ),
        None,
    )


def slot_label(slot: ForecastSlot) -> str:
    """Return a short label for a forecast slot."""
    return f"{slot.direction} von {slot.start} bis {slot.end}"


def slot_start_datetime(slot: ForecastSlot) -> datetime | None:
    """Return the slot start as datetime."""
    if slot.start_iso is None:
        return None
    return datetime.fromisoformat(slot.start_iso)


def slot_matches_direction(slot: ForecastSlot, direction: str) -> bool:
    """Return whether a slot includes a direction."""
    return direction in {part.strip() for part in slot.direction.split("/")}


def starts_in_minutes(slot: ForecastSlot, now: datetime) -> int | None:
    """Return minutes until a slot starts."""
    start = slot_start_datetime(slot)
    if start is None:
        return None
    return ceil((start - now).total_seconds() / 60)


def _is_upcoming(slot: ForecastSlot, now: datetime) -> bool:
    minutes = starts_in_minutes(slot, now)
    return minutes is not None and minutes >= 0


def without_none(values: dict[str, Any]) -> dict[str, Any]:
    """Return a copy without None values."""
    return {key: value for key, value in values.items() if value is not None}
