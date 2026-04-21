"""Sensor platform for FRA Betriebsrichtung."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FraBetriebsrichtungConfigEntry
from .const import (
    ATTR_CURRENT_SINCE,
    ATTR_LABEL,
    ATTR_LAST_UPDATE,
    ATTR_NEXT_SLOT,
    ATTR_SLOTS,
    ATTR_SOURCE,
    ATTR_SUMMARY,
    DOMAIN,
    UMWELTHAUS_URL,
)
from .coordinator import FraBetriebsrichtungCoordinator
from .parser import FraBetriebsrichtungData, normalize_direction


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
        }
    )


def _forecast_attrs(data: FraBetriebsrichtungData) -> dict[str, Any]:
    next_slot = data.forecast_slots[0].as_dict() if data.forecast_slots else None
    return {
        ATTR_SUMMARY: data.forecast_summary,
        ATTR_NEXT_SLOT: next_slot,
        ATTR_SLOTS: [slot.as_dict() for slot in data.forecast_slots],
        ATTR_SOURCE: data.source,
        ATTR_LAST_UPDATE: data.last_update,
    }


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
    async_add_entities(
        FraBetriebsrichtungSensor(coordinator, description) for description in SENSORS
    )


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
