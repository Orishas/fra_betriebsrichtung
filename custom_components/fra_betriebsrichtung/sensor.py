"""Sensor platform for FRA Betriebsrichtung."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FraBetriebsrichtungConfigEntry
from .const import (
    ATTR_CURRENT_SINCE,
    ATTR_CURRENT_SINCE_START,
    ATTR_CURRENT_DURATION_MINUTES,
    ATTR_DATE,
    ATTR_DIRECTION,
    ATTR_END,
    ATTR_ERRORS,
    ATTR_FALLBACK_OK,
    ATTR_FALLBACK_USED,
    ATTR_FROM,
    ATTR_LABEL,
    ATTR_LAST_UPDATE,
    ATTR_LAST_SUCCESS,
    ATTR_NEXT_SLOT,
    ATTR_NEXT_SLOT_LABEL,
    ATTR_NOISE_DIRECTION,
    ATTR_PRIMARY_OK,
    ATTR_SLOTS,
    ATTR_SOURCE,
    ATTR_SUMMARY,
    ATTR_TO,
    CONF_NOISE_DIRECTION,
    DEFAULT_NOISE_DIRECTION,
    DOMAIN,
    UMWELTHAUS_URL,
)
from .coordinator import FraBetriebsrichtungCoordinator
from .parser import ForecastSlot, FraBetriebsrichtungData, normalize_direction


@dataclass(frozen=True, kw_only=True)
class FraSensorEntityDescription(SensorEntityDescription):
    """Describes a FRA Betriebsrichtung sensor."""

    value_fn: Callable[[FraBetriebsrichtungData], str | None]
    attrs_fn: Callable[[FraBetriebsrichtungData], dict[str, Any]]


def _current_value(data: FraBetriebsrichtungData) -> str | None:
    return data.current_direction


def _forecast_value(data: FraBetriebsrichtungData) -> str | None:
    if data.forecast_slots:
        return data.forecast_slots[0].direction
    if direction := normalize_direction(data.forecast_summary):
        return direction
    return _short_state(data.forecast_summary)


def _current_attrs(data: FraBetriebsrichtungData) -> dict[str, Any]:
    return _without_none(
        {
            ATTR_LABEL: data.current_label,
            ATTR_SOURCE: data.source,
            ATTR_LAST_UPDATE: data.last_update,
            ATTR_CURRENT_SINCE: data.current_since,
            ATTR_CURRENT_SINCE_START: data.current_since_start,
            ATTR_CURRENT_DURATION_MINUTES: data.current_duration_minutes,
            **_health_attrs(data),
        }
    )


def _forecast_attrs(data: FraBetriebsrichtungData) -> dict[str, Any]:
    next_slot = data.forecast_slots[0].as_dict() if data.forecast_slots else None
    return _without_none(
        {
            ATTR_SUMMARY: data.forecast_summary,
            ATTR_NEXT_SLOT: next_slot,
            ATTR_NEXT_SLOT_LABEL: _slot_label(data.forecast_slots[0])
            if data.forecast_slots
            else None,
            ATTR_SLOTS: [slot.as_dict() for slot in data.forecast_slots],
            ATTR_SOURCE: data.source,
            ATTR_LAST_UPDATE: data.last_update,
            **_health_attrs(data),
        }
    )


SENSORS: tuple[FraSensorEntityDescription, ...] = (
    FraSensorEntityDescription(
        key="aktuell",
        translation_key="current",
        icon="mdi:airplane-takeoff",
        value_fn=_current_value,
        attrs_fn=_current_attrs,
    ),
    FraSensorEntityDescription(
        key="forecast",
        translation_key="forecast",
        icon="mdi:calendar-clock",
        value_fn=_forecast_value,
        attrs_fn=_forecast_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FRA Betriebsrichtung sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = [
        FraBetriebsrichtungSensor(coordinator, description) for description in SENSORS
    ]
    entities.append(FraNextNoiseSensor(entry, coordinator))
    async_add_entities(entities)


class FraBetriebsrichtungSensor(
    CoordinatorEntity[FraBetriebsrichtungCoordinator],
    SensorEntity,
):
    """Representation of a FRA Betriebsrichtung sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FraBetriebsrichtungCoordinator,
        description: FraSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self._attr_device_info = {
            "configuration_url": UMWELTHAUS_URL,
            "identifiers": {(DOMAIN, "frankfurt_airport")},
            "manufacturer": "FRA Betriebsrichtung",
            "name": "Frankfurt Airport",
        }

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return f"{DOMAIN}_{self.entity_description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> str | None:
        """Return the sensor state."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        if self.coordinator.data is None:
            return {}
        return self.entity_description.attrs_fn(self.coordinator.data)


def _short_state(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 250:
        return value
    return f"{value[:247]}..."


def _without_none(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


class FraNextNoiseSensor(
    CoordinatorEntity[FraBetriebsrichtungCoordinator],
    SensorEntity,
):
    """Sensor for the next forecast period matching the local noise direction."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    entity_description = SensorEntityDescription(
        key="naechster_fluglaerm",
        translation_key="next_noise",
        icon="mdi:calendar-alert",
    )

    def __init__(
        self,
        entry: FraBetriebsrichtungConfigEntry,
        coordinator: FraBetriebsrichtungCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_naechster_fluglaerm"
        self._attr_device_info = {
            "configuration_url": UMWELTHAUS_URL,
            "identifiers": {(DOMAIN, "frankfurt_airport")},
            "manufacturer": "FRA Betriebsrichtung",
            "name": "Frankfurt Airport",
        }

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return f"{DOMAIN}_naechster_fluglaerm"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> datetime | None:
        """Return the start of the next noise forecast slot."""
        slot = _next_noise_slot(self.coordinator.data, self._noise_direction)
        if slot is None or slot.start_iso is None:
            return None
        return datetime.fromisoformat(slot.start_iso)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        slot = _next_noise_slot(data, self._noise_direction)
        slot_data = slot.as_dict() if slot else {}
        return _without_none(
            {
                ATTR_NOISE_DIRECTION: self._noise_direction,
                ATTR_NEXT_SLOT: slot_data or None,
                ATTR_DIRECTION: slot_data.get("direction"),
                ATTR_FROM: slot_data.get("from"),
                ATTR_TO: slot_data.get("to"),
                ATTR_DATE: slot_data.get("date"),
                ATTR_END: slot_data.get("end"),
                ATTR_SOURCE: data.source if data else None,
                ATTR_LAST_UPDATE: data.last_update if data else None,
                **(_health_attrs(data) if data else {}),
            }
        )

    @property
    def _noise_direction(self) -> str:
        """Return the configured local noise direction."""
        return self._entry.options.get(CONF_NOISE_DIRECTION, DEFAULT_NOISE_DIRECTION)


def _health_attrs(data: FraBetriebsrichtungData) -> dict[str, Any]:
    return {
        ATTR_PRIMARY_OK: data.primary_ok,
        ATTR_FALLBACK_OK: data.fallback_ok,
        ATTR_FALLBACK_USED: data.fallback_used,
        ATTR_LAST_SUCCESS: data.last_success,
        ATTR_ERRORS: list(data.errors) or None,
    }


def _slot_label(slot: ForecastSlot) -> str:
    return f"{slot.direction} von {slot.start} bis {slot.end}"


def _next_noise_slot(
    data: FraBetriebsrichtungData | None,
    noise_direction: str,
) -> ForecastSlot | None:
    if data is None:
        return None
    return next(
        (
            slot
            for slot in data.forecast_slots
            if _slot_matches_direction(slot, noise_direction)
        ),
        None,
    )


def _slot_matches_direction(slot: ForecastSlot, direction: str) -> bool:
    return direction in {part.strip() for part in slot.direction.split("/")}
