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
from homeassistant.util import dt as dt_util

from . import FraBetriebsrichtungConfigEntry
from .const import (
    ATTR_CURRENT_DIRECTION,
    ATTR_FORECAST_DIRECTION,
    ATTR_LAST_UPDATE,
    ATTR_NEXT_SLOT,
    ATTR_NOISE_DIRECTION,
    ATTR_SOURCE,
    ATTR_STARTS_IN_MINUTES,
    ATTR_WARNING_MINUTES,
    DOMAIN,
)
from .coordinator import FraBetriebsrichtungCoordinator
from .entity import (
    configured_noise_direction,
    configured_warning_minutes,
    device_info,
    first_forecast_slot,
    next_upcoming_noise_slot,
    slot_matches_direction,
    starts_in_minutes,
    suggested_object_id,
)


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
            FraBetriebsrichtungSoonNoiseSensor(
                entry,
                entry.runtime_data.coordinator,
            ),
            FraBetriebsrichtungDirectionChangeForecastSensor(
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
        self._attr_device_info = device_info()

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return suggested_object_id("fluglaerm")

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
        return configured_noise_direction(self._entry)


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
        self._attr_device_info = device_info()

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return suggested_object_id("fluglaerm_forecast")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and first_forecast_slot(self.coordinator.data) is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the next forecast direction matches local noise."""
        slot = first_forecast_slot(self.coordinator.data)
        if not self.available or slot is None:
            return None
        return slot_matches_direction(slot, self._noise_direction)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        slot = first_forecast_slot(data)
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
        return configured_noise_direction(self._entry)


class FraBetriebsrichtungSoonNoiseSensor(
    CoordinatorEntity[FraBetriebsrichtungCoordinator],
    BinarySensorEntity,
):
    """Binary sensor indicating whether aircraft noise is expected soon."""

    _attr_has_entity_name = True
    entity_description = BinarySensorEntityDescription(
        key="fluglaerm_bald",
        translation_key="aircraft_noise_soon",
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
        self._attr_unique_id = f"{DOMAIN}_fluglaerm_bald"
        self._attr_device_info = device_info()

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return suggested_object_id("fluglaerm_bald")

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
        """Return true if local aircraft noise is forecast soon."""
        data = self.coordinator.data
        if not self.available or data is None:
            return None
        if data.current_direction == self._noise_direction:
            return False

        now = dt_util.now()
        slot = next_upcoming_noise_slot(data, self._noise_direction, now)
        if slot is None:
            return False
        starts_in = starts_in_minutes(slot, now)
        return starts_in is not None and starts_in <= self._warning_minutes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        now = dt_util.now()
        slot = (
            next_upcoming_noise_slot(data, self._noise_direction, now)
            if data
            else None
        )
        return {
            ATTR_WARNING_MINUTES: self._warning_minutes,
            ATTR_STARTS_IN_MINUTES: starts_in_minutes(slot, now)
            if slot
            else None,
            ATTR_NOISE_DIRECTION: self._noise_direction,
            ATTR_NEXT_SLOT: slot.as_dict() if slot else None,
            ATTR_SOURCE: data.source if data else None,
            ATTR_LAST_UPDATE: data.last_update if data else None,
        }

    @property
    def _noise_direction(self) -> str:
        """Return the configured local noise direction."""
        return configured_noise_direction(self._entry)

    @property
    def _warning_minutes(self) -> int:
        """Return the configured warning window."""
        return configured_warning_minutes(self._entry)


class FraBetriebsrichtungDirectionChangeForecastSensor(
    CoordinatorEntity[FraBetriebsrichtungCoordinator],
    BinarySensorEntity,
):
    """Binary sensor indicating whether the next forecast slot changes direction."""

    _attr_has_entity_name = True
    entity_description = BinarySensorEntityDescription(
        key="richtungswechsel_forecast",
        translation_key="direction_change_forecast",
        icon="mdi:swap-horizontal",
    )

    def __init__(
        self,
        coordinator: FraBetriebsrichtungCoordinator,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_richtungswechsel_forecast"
        self._attr_device_info = device_info()

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return suggested_object_id("richtungswechsel_forecast")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        data = self.coordinator.data
        return (
            super().available
            and data is not None
            and data.current_direction is not None
            and first_forecast_slot(data) is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the next forecast slot differs from the current direction."""
        data = self.coordinator.data
        slot = first_forecast_slot(data)
        if not self.available or data is None or slot is None:
            return None
        return not slot_matches_direction(slot, data.current_direction)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        slot = first_forecast_slot(data)
        return {
            ATTR_CURRENT_DIRECTION: data.current_direction if data else None,
            ATTR_FORECAST_DIRECTION: slot.direction if slot else None,
            ATTR_NEXT_SLOT: slot.as_dict() if slot else None,
            ATTR_SOURCE: data.source if data else None,
            ATTR_LAST_UPDATE: data.last_update if data else None,
        }
