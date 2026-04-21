"""Config flow for FRA Betriebsrichtung."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_NOISE_DIRECTION,
    DEFAULT_NOISE_DIRECTION,
    DOMAIN,
)

NOISE_DIRECTION_OPTIONS = {
    "br_07": "BR 07",
    "br_25": "BR 25",
}
DIRECTION_TO_OPTION = {value: key for key, value in NOISE_DIRECTION_OPTIONS.items()}


def _noise_direction_schema(default: str = DEFAULT_NOISE_DIRECTION) -> vol.Schema:
    """Return the setup/options schema."""
    default_option = DIRECTION_TO_OPTION.get(
        default,
        DIRECTION_TO_OPTION[DEFAULT_NOISE_DIRECTION],
    )
    return vol.Schema(
        {
            vol.Required(CONF_NOISE_DIRECTION, default=default_option): SelectSelector(
                SelectSelectorConfig(
                    options=list(NOISE_DIRECTION_OPTIONS),
                    mode=SelectSelectorMode.LIST,
                    translation_key=CONF_NOISE_DIRECTION,
                )
            )
        }
    )


class FraBetriebsrichtungConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FRA Betriebsrichtung."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> FraBetriebsrichtungOptionsFlow:
        """Create the options flow."""
        return FraBetriebsrichtungOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="FRA Betriebsrichtung",
                data={},
                options={
                    CONF_NOISE_DIRECTION: NOISE_DIRECTION_OPTIONS[
                        user_input[CONF_NOISE_DIRECTION]
                    ],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_noise_direction_schema(),
        )


class FraBetriebsrichtungOptionsFlow(OptionsFlow):
    """Handle options for FRA Betriebsrichtung."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_NOISE_DIRECTION: NOISE_DIRECTION_OPTIONS[
                        user_input[CONF_NOISE_DIRECTION]
                    ],
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_noise_direction_schema(
                self.config_entry.options.get(
                    CONF_NOISE_DIRECTION,
                    DEFAULT_NOISE_DIRECTION,
                )
            ),
        )
