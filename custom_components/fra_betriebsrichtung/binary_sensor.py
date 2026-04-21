"""Binary sensor platform for FRA Betriebsrichtung."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FraBetriebsrichtungConfigEntry
from .const import (
    ATTR_CURRENT_DIRECTION,
    ATTR_FORECAST_DIRECTION,
    ATTR_LAST_UPDATE,
    ATTR_NEXT_SLOT,
    ATTR_NOISE_DIRECTION,
    ATTR_SOURCE,
    CONF_NOISE_DIRECTION,
    DEFAULT_NOISE_DIRECTION,
    DOMAIN,
    UMWELTHAUS_URL,
)
from .coordinator import FraBetriebsrichtungCoordinator
from .parser import ForecastSlot, FraBetriebsrichtungData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FRA Betriebsrichtung binary sensors."""
    async_add_entities(
        [
            FraBetriebsrichtungNoiseSensor(
                entry,
                entry.runtime_data.coordinator,
            ),
            FraBetriebsrichtungForecastNoiseSensor(
                entry,
                entry.runtime_data.coordinator,
            ),
        ]
    )


class FraBetriebsrichtungNoiseSensor(
    CoordinatorEntity[FraBetriebsrichtungCoordinator],
    BinarySensorEntity,
):
    """Binary sensor indicating whether the current direction causes local noise."""

    _attr_has_entity_name = True
    entity_description = BinarySensorEntityDescription(
        key="fluglaerm",
        translation_key="aircraft_noise",
        icon="mdi:airplane-alert",
    )

    def __init__(
        self,
        entry: FraBetriebsrichtungConfigEntry,
        coordinator: FraBetriebsrichtungCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_fluglaerm"
        self._attr_device_info = {
            "configuration_url": UMWELTHAUS_URL,
            "identifiers": {(DOMAIN, "frankfurt_airport")},
            "manufacturer": "FRA Betriebsrichtung",
            "name": "Frankfurt Airport",
        }

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return f"{DOMAIN}_fluglaerm"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.current_direction is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the configured noise direction is currently active."""
        if not self.available or self.coordinator.data is None:
            return None
        return self.coordinator.data.current_direction == self._noise_direction

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        return {
            ATTR_NOISE_DIRECTION: self._noise_direction,
            ATTR_CURRENT_DIRECTION: data.current_direction if data else None,
            ATTR_SOURCE: data.source if data else None,
            ATTR_LAST_UPDATE: data.last_update if data else None,
        }

    @property
    def _noise_direction(self) -> str:
        """Return the configured local noise direction."""
        return self._entry.options.get(CONF_NOISE_DIRECTION, DEFAULT_NOISE_DIRECTION)


class FraBetriebsrichtungForecastNoiseSensor(
    CoordinatorEntity[FraBetriebsrichtungCoordinator],
    BinarySensorEntity,
):
    """Binary sensor indicating whether the next forecast slot causes noise."""

    _attr_has_entity_name = True
    entity_description = BinarySensorEntityDescription(
        key="fluglaerm_forecast",
        translation_key="aircraft_noise_forecast",
        icon="mdi:airplane-clock",
    )

    def __init__(
        self,
        entry: FraBetriebsrichtungConfigEntry,
        coordinator: FraBetriebsrichtungCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_fluglaerm_forecast"
        self._attr_device_info = {
            "configuration_url": UMWELTHAUS_URL,
            "identifiers": {(DOMAIN, "frankfurt_airport")},
            "manufacturer": "FRA Betriebsrichtung",
            "name": "Frankfurt Airport",
        }

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return f"{DOMAIN}_fluglaerm_forecast"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and _next_slot(self.coordinator.data) is not None

    @property
    def is_on(self) -> bool | None:
        """Return true if the next forecast direction matches local noise."""
        slot = _next_slot(self.coordinator.data)
        if not self.available or slot is None:
            return None
        return _slot_matches_direction(slot, self._noise_direction)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        slot = _next_slot(data)
        return {
            ATTR_NOISE_DIRECTION: self._noise_direction,
            ATTR_FORECAST_DIRECTION: slot.direction if slot else None,
            ATTR_NEXT_SLOT: slot.as_dict() if slot else None,
            ATTR_SOURCE: data.source if data else None,
            ATTR_LAST_UPDATE: data.last_update if data else None,
        }

    @property
    def _noise_direction(self) -> str:
        """Return the configured local noise direction."""
        return self._entry.options.get(CONF_NOISE_DIRECTION, DEFAULT_NOISE_DIRECTION)


def _next_slot(data: FraBetriebsrichtungData | None) -> ForecastSlot | None:
    if data is None or not data.forecast_slots:
        return None
    return data.forecast_slots[0]


def _slot_matches_direction(slot: ForecastSlot, direction: str) -> bool:
    return direction in {part.strip() for part in slot.direction.split("/")}
