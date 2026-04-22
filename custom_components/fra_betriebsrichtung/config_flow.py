"""Config flow for FRA Betriebsrichtung."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_NOISE_DIRECTION,
    CONF_WARNING_MINUTES,
    DEFAULT_NOISE_DIRECTION,
    DEFAULT_WARNING_MINUTES,
    DOMAIN,
    MAX_WARNING_MINUTES,
    MIN_WARNING_MINUTES,
    WARNING_MINUTES_STEP,
)

NOISE_DIRECTION_OPTIONS = {
    "br_07": "BR 07",
    "br_25": "BR 25",
}
DIRECTION_TO_OPTION = {value: key for key, value in NOISE_DIRECTION_OPTIONS.items()}


def _noise_direction_schema(default: str = DEFAULT_NOISE_DIRECTION) -> vol.Schema:
    """Return the setup/options schema."""
    return _options_schema(default, DEFAULT_WARNING_MINUTES)


def _options_schema(
    default_noise_direction: str = DEFAULT_NOISE_DIRECTION,
    default_warning_minutes: int = DEFAULT_WARNING_MINUTES,
) -> vol.Schema:
    """Return the setup/options schema."""
    default_option = DIRECTION_TO_OPTION.get(
        default_noise_direction,
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
            ),
            vol.Required(
                CONF_WARNING_MINUTES,
                default=default_warning_minutes,
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_WARNING_MINUTES,
                    max=MAX_WARNING_MINUTES,
                    step=WARNING_MINUTES_STEP,
                    mode=NumberSelectorMode.BOX,
                )
            ),
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
                    CONF_WARNING_MINUTES: user_input[CONF_WARNING_MINUTES],
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
                    CONF_WARNING_MINUTES: user_input[CONF_WARNING_MINUTES],
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                self.config_entry.options.get(
                    CONF_NOISE_DIRECTION,
                    DEFAULT_NOISE_DIRECTION,
                ),
                self.config_entry.options.get(
                    CONF_WARNING_MINUTES,
                    DEFAULT_WARNING_MINUTES,
                ),
            ),
        )
