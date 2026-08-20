"""Dashboard card registration tests for FRA Betriebsrichtung."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.fra_betriebsrichtung import frontend as frontend_module
from custom_components.fra_betriebsrichtung.const import (
    CARD_FILENAME,
    CARD_URL_PATH,
    DATA_CARD_REGISTERED,
)


def _hass(static_paths: list[Any]) -> SimpleNamespace:
    async def async_register_static_paths(configs: list[Any]) -> None:
        static_paths.extend(configs)

    async def async_add_executor_job(func, *args):
        return func(*args)

    return SimpleNamespace(
        data={},
        http=SimpleNamespace(async_register_static_paths=async_register_static_paths),
        async_add_executor_job=async_add_executor_job,
    )


def test_card_file_is_bundled() -> None:
    """The card is shipped inside the integration folder."""
    card = (
        Path(frontend_module.__file__).parent / "www" / CARD_FILENAME
    )
    assert card.is_file()
    assert "fra-betriebsrichtung-card" in card.read_text(encoding="utf-8")


def test_register_card_serves_and_registers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The card is served as a static path and added as a frontend resource."""
    urls: list[str] = []
    monkeypatch.setattr(
        frontend_module,
        "add_extra_js_url",
        lambda hass, url: urls.append(url),
    )

    static_paths: list[Any] = []
    hass = _hass(static_paths)

    asyncio.run(frontend_module.async_register_card(hass))

    assert static_paths[0][0] == CARD_URL_PATH
    assert static_paths[0][1].endswith(CARD_FILENAME)
    assert urls == [f"{CARD_URL_PATH}?v=0.0.0-test"]
    assert hass.data[DATA_CARD_REGISTERED] is True


def test_register_card_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """A second call does not register the card twice."""
    urls: list[str] = []
    monkeypatch.setattr(
        frontend_module,
        "add_extra_js_url",
        lambda hass, url: urls.append(url),
    )

    static_paths: list[Any] = []
    hass = _hass(static_paths)

    asyncio.run(frontend_module.async_register_card(hass))
    asyncio.run(frontend_module.async_register_card(hass))

    assert len(static_paths) == 1
    assert len(urls) == 1


def test_register_card_without_bundle_does_not_register(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing card file is logged, not raised."""
    urls: list[str] = []
    monkeypatch.setattr(
        frontend_module,
        "add_extra_js_url",
        lambda hass, url: urls.append(url),
    )
    monkeypatch.setattr(frontend_module, "CARD_FILENAME", "does-not-exist.js")

    static_paths: list[Any] = []
    hass = _hass(static_paths)

    asyncio.run(frontend_module.async_register_card(hass))

    assert not static_paths
    assert not urls
    assert DATA_CARD_REGISTERED not in hass.data
