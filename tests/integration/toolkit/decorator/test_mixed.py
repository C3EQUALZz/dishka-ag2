"""Sync and async tools registered through Toolkit decorators."""

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig
from ag2.tools import Toolkit

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.toolkit.common import ToolkitProvider, WeatherService


@pytest.mark.asyncio()
async def test_toolkit_decorators_with_mixed_tools() -> None:
    calls: list[tuple[str, WeatherService]] = []
    toolkit = Toolkit()

    @toolkit.tool
    @inject
    def sync_weather(city: str, weather: FromDishka[WeatherService]) -> str:
        calls.append(("sync", weather))
        return weather.forecast(city)

    @toolkit.tool
    @inject
    async def async_weather(city: str, weather: FromDishka[WeatherService]) -> str:
        calls.append(("async", weather))
        return weather.forecast(city)

    async with async_env(ToolkitProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="sync_weather", arguments='{"city": "Berlin"}'),
                ToolCallEvent(name="async_weather", arguments='{"city": "Tokyo"}'),
                "Done.",
            ),
            tools=[toolkit],
            middleware=[middleware],
        )
        await agent.ask("Get both forecasts.")

    assert [name for name, _ in calls] == ["sync", "async"]
    sync_service, async_service = (service for _, service in calls)
    assert sync_service.session is async_service.session
    assert sync_service.request.request_id != async_service.request.request_id
    assert sync_service.request.tool_name == "sync_weather"
    assert async_service.request.tool_name == "async_weather"
