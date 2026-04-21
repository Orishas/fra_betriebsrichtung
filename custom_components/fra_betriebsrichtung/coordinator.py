"""Coordinator for FRA Betriebsrichtung."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientSession

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    FALLBACK_URL,
    UMWELTHAUS_URL,
    UPDATE_INTERVAL,
)
from .parser import (
    FraBetriebsrichtungData,
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

    async def _async_update_data(self) -> FraBetriebsrichtungData:
        """Fetch data from the configured HTML sources."""
        primary: FraBetriebsrichtungData | None = None
        fallback: FraBetriebsrichtungData | None = None
        errors: list[str] = []

        try:
            primary = parse_umwelthaus(await self._fetch_text(UMWELTHAUS_URL))
        except Exception as err:  # noqa: BLE001 - parser/network failures are recoverable
            errors.append(f"Umwelthaus: {err}")
            _LOGGER.debug("Failed to parse primary source", exc_info=err)

        if primary is None or not (primary.has_current and primary.has_forecast):
            try:
                fallback = parse_fallback(await self._fetch_text(FALLBACK_URL))
            except Exception as err:  # noqa: BLE001 - parser/network failures are recoverable
                errors.append(f"betriebsrichtungsprognose.de: {err}")
                _LOGGER.debug("Failed to parse fallback source", exc_info=err)

        data = merge_data(primary, fallback)
        if data is not None and data.has_any_data:
            return data

        message = "; ".join(errors) if errors else "No usable operating direction data"
        raise UpdateFailed(message)

    async def _fetch_text(self, url: str) -> str:
        """Fetch a source page as text."""
        async with asyncio.timeout(REQUEST_TIMEOUT):
            async with self._session.get(url, headers=REQUEST_HEADERS) as response:
                response.raise_for_status()
                return await response.text()
