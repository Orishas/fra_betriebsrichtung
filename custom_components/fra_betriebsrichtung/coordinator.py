"""Coordinator for FRA Betriebsrichtung."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging

from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NOISE_DIRECTION,
    DEFAULT_NOISE_DIRECTION,
    DOMAIN,
    EVENT_DIRECTION_CHANGED,
    FALLBACK_URL,
    UMWELTHAUS_URL,
    UPDATE_INTERVAL,
)
from .models import FraBetriebsrichtungData, SourceHealth
from .parser import (
    merge_data,
    parse_fallback,
    parse_umwelthaus,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15
REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "HomeAssistant/fra_betriebsrichtung",
}


class FraBetriebsrichtungCoordinator(DataUpdateCoordinator[FraBetriebsrichtungData]):
    """Fetch and normalize FRA operating direction data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self._session = session
        self._entry = entry

    async def _async_update_data(self) -> FraBetriebsrichtungData:
        """Fetch data from the configured HTML sources."""
        primary: FraBetriebsrichtungData | None = None
        fallback: FraBetriebsrichtungData | None = None
        errors: list[str] = []
        fallback_attempted = False
        previous_direction = self.data.current_direction if self.data else None

        try:
            primary = parse_umwelthaus(await self._fetch_text(UMWELTHAUS_URL))
        except Exception as err:  # noqa: BLE001 - parser/network failures are recoverable
            errors.append(f"Umwelthaus: {err}")
            _LOGGER.debug("Failed to parse primary source", exc_info=err)

        if primary is None or not (primary.has_current and primary.has_forecast):
            fallback_attempted = True
            try:
                fallback = parse_fallback(await self._fetch_text(FALLBACK_URL))
            except Exception as err:  # noqa: BLE001 - parser/network failures are recoverable
                errors.append(f"betriebsrichtungsprognose.de: {err}")
                _LOGGER.debug("Failed to parse fallback source", exc_info=err)

        data = merge_data(primary, fallback)
        if data is not None and data.has_any_data:
            data = replace(
                data,
                health=SourceHealth(
                    primary_ok=primary is not None and primary.has_any_data,
                    fallback_ok=(
                        fallback is not None and fallback.has_any_data
                        if fallback_attempted
                        else None
                    ),
                    fallback_used=(primary is None and fallback is not None)
                    or data.fallback_used,
                    last_success=dt_util.now().isoformat(),
                    errors=tuple(errors),
                ),
            )
            self._fire_direction_changed(previous_direction, data)
            return data

        message = "; ".join(errors) if errors else "No usable operating direction data"
        raise UpdateFailed(message)

    async def _fetch_text(self, url: str) -> str:
        """Fetch a source page as text."""
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with self._session.get(url, headers=REQUEST_HEADERS) as response:
                response.raise_for_status()
                return await response.text()

    def _fire_direction_changed(
        self,
        previous_direction: str | None,
        data: FraBetriebsrichtungData,
    ) -> None:
        """Fire an event when the current direction changes."""
        current_direction = data.current_direction
        if previous_direction is None or current_direction is None:
            return
        if previous_direction == current_direction:
            return

        noise_direction = self._entry.options.get(
            CONF_NOISE_DIRECTION,
            DEFAULT_NOISE_DIRECTION,
        )
        self.hass.bus.async_fire(
            EVENT_DIRECTION_CHANGED,
            {
                "old_direction": previous_direction,
                "new_direction": current_direction,
                "noise_direction": noise_direction,
                "noise_active": current_direction == noise_direction,
                "source": data.source,
                "last_update": data.last_update,
                "current_since": data.current_since,
                "next_slot": data.forecast_slots[0].as_dict()
                if data.forecast_slots
                else None,
            },
        )
