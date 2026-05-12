"""Binary sensor platform for FRA Betriebsrichtung."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
    next_noise_slot,
    starts_in_minutes,
    suggested_object_id,
)
from .models import FraBetriebsrichtungData


@dataclass(frozen=True)
class BinarySensorRenderConfig:
    """Per-entity configuration injected into description callables.

    Intentionally *not* named ``BinarySensorContext`` and *not* exposed as
    ``Entity._context`` — that name is reserved by Home Assistant's
    ``Entity`` base class for the state-change ``homeassistant.core.Context``.
    Shadowing it produces AttributeError crashes during state serialisation.
    """

    noise_direction: str
    warning_minutes: int


@dataclass(frozen=True, kw_only=True)
class FraBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a FRA Betriebsrichtung binary sensor."""

    is_on_fn: Callable[[FraBetriebsrichtungData, BinarySensorRenderConfig], bool | None]
    attrs_fn: Callable[
        [FraBetriebsrichtungData, BinarySensorRenderConfig], dict[str, Any]
    ]
    available_fn: Callable[[FraBetriebsrichtungData | None], bool] = (
        lambda data: data is not None and data.current_direction is not None
    )


def _aircraft_noise_is_on(
    data: FraBetriebsrichtungData,
    config: BinarySensorRenderConfig,
) -> bool:
    return data.current_direction == config.noise_direction


def _aircraft_noise_attrs(
    data: FraBetriebsrichtungData,
    config: BinarySensorRenderConfig,
) -> dict[str, Any]:
    return {
        ATTR_NOISE_DIRECTION: config.noise_direction,
        ATTR_CURRENT_DIRECTION: data.current_direction,
        ATTR_SOURCE: data.source,
        ATTR_LAST_UPDATE: data.last_update,
    }


def _aircraft_noise_warning_is_on(
    data: FraBetriebsrichtungData,
    config: BinarySensorRenderConfig,
) -> bool:
    if data.current_direction == config.noise_direction:
        return False
    now = dt_util.now()
    slot = next_noise_slot(data, config.noise_direction, now)
    if slot is None:
        return False
    minutes_until = starts_in_minutes(slot, now)
    return minutes_until is not None and minutes_until <= config.warning_minutes


def _aircraft_noise_warning_attrs(
    data: FraBetriebsrichtungData,
    config: BinarySensorRenderConfig,
) -> dict[str, Any]:
    now = dt_util.now()
    slot = next_noise_slot(data, config.noise_direction, now)
    return {
        ATTR_WARNING_MINUTES: config.warning_minutes,
        ATTR_STARTS_IN_MINUTES: starts_in_minutes(slot, now) if slot else None,
        ATTR_NOISE_DIRECTION: config.noise_direction,
        ATTR_NEXT_SLOT: slot.as_dict() if slot else None,
        ATTR_SOURCE: data.source,
        ATTR_LAST_UPDATE: data.last_update,
    }


BINARY_SENSORS: tuple[FraBinarySensorEntityDescription, ...] = (
    FraBinarySensorEntityDescription(
        key="aircraft_noise",
        translation_key="aircraft_noise",
        icon="mdi:airplane-alert",
        is_on_fn=_aircraft_noise_is_on,
        attrs_fn=_aircraft_noise_attrs,
    ),
    FraBinarySensorEntityDescription(
        key="aircraft_noise_warning",
        translation_key="aircraft_noise_warning",
        icon="mdi:airplane-clock",
        is_on_fn=_aircraft_noise_warning_is_on,
        attrs_fn=_aircraft_noise_warning_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FraBetriebsrichtungConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FRA Betriebsrichtung binary sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        FraBinarySensor(entry, coordinator, description)
        for description in BINARY_SENSORS
    )


class FraBinarySensor(
    CoordinatorEntity[FraBetriebsrichtungCoordinator],
    BinarySensorEntity,
):
    """Representation of a FRA Betriebsrichtung binary sensor."""

    _attr_has_entity_name = True
    entity_description: FraBinarySensorEntityDescription

    def __init__(
        self,
        entry: FraBetriebsrichtungConfigEntry,
        coordinator: FraBetriebsrichtungCoordinator,
        description: FraBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{description.key}"
        self._attr_device_info = device_info()
        # Cache the per-entity render config once. Must not be exposed as
        # ``_context`` — that attribute name is owned by Entity for the HA
        # state-change Context.
        self._render_config = BinarySensorRenderConfig(
            noise_direction=configured_noise_direction(entry),
            warning_minutes=configured_warning_minutes(entry),
        )

    @property
    def suggested_object_id(self) -> str:
        """Return a stable, language-independent entity object id."""
        return suggested_object_id(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        if not self.available or self.coordinator.data is None:
            return None
        return self.entity_description.is_on_fn(
            self.coordinator.data, self._render_config
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity attributes."""
        data = self.coordinator.data
        if data is None:
            return {}
        return self.entity_description.attrs_fn(data, self._render_config)
