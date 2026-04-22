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
    ATTR_FROM,
    ATTR_LABEL,
    ATTR_LAST_UPDATE,
    ATTR_NEXT_SLOT,
    ATTR_NEXT_SLOT_LABEL,
    ATTR_NOISE_DIRECTION,
    ATTR_SLOTS,
    ATTR_SOURCE,
    ATTR_SUMMARY,
    ATTR_TO,
    DOMAIN,
)
from .coordinator import FraBetriebsrichtungCoordinator
from .entity import (
    configured_noise_direction,
    device_info,
    health_attributes,
    next_noise_slot,
    slot_label,
    suggested_object_id,
    without_none,
)
from .models import FraBetriebsrichtungData
from .parser import normalize_direction


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
    return without_none(
        {
            ATTR_LABEL: data.current_label,
            ATTR_SOURCE: data.source,
            ATTR_LAST_UPDATE: data.last_update,
            ATTR_CURRENT_SINCE: data.current_since,
            ATTR_CURRENT_SINCE_START: data.current_since_start,
            ATTR_CURRENT_DURATION_MINUTES: data.current_duration_minutes,
            **health_attributes(data),
        }
    )


def _forecast_attrs(data: FraBetriebsrichtungData) -> dict[str, Any]:
    next_slot = data.forecast_slots[0].as_dict() if data.forecast_slots else None
    return without_none(
        {
            ATTR_SUMMARY: data.forecast_summary,
            ATTR_NEXT_SLOT: next_slot,
            ATTR_NEXT_SLOT_LABEL: slot_label(data.forecast_slots[0])
            if data.forecast_slots
            else None,
            ATTR_SLOTS: [slot.as_dict() for slot in data.forecast_slots],
            ATTR_SOURCE: data.source,
            ATTR_LAST_UPDATE: data.last_update,
            **health_attributes(data),
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
        self._attr_device_info = device_info()

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return suggested_object_id(self.entity_description.key)

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
        self._attr_device_info = device_info()

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return suggested_object_id("naechster_fluglaerm")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> datetime | None:
        """Return the start of the next noise forecast slot."""
        slot = next_noise_slot(self.coordinator.data, self._noise_direction)
        if slot is None or slot.start_iso is None:
            return None
        return datetime.fromisoformat(slot.start_iso)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        slot = next_noise_slot(data, self._noise_direction)
        slot_data = slot.as_dict() if slot else {}
        return without_none(
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
                **(health_attributes(data) if data else {}),
            }
        )

    @property
    def _noise_direction(self) -> str:
        """Return the configured local noise direction."""
        return configured_noise_direction(self._entry)
