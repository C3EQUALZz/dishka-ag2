"""Toolkit(...tools) with sync Dishka middleware."""

from typing import TYPE_CHECKING

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import Toolkit

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import sync_env
from tests.integration.toolkit.common import ToolkitProvider, WeatherService

if TYPE_CHECKING:
    from uuid import UUID


@pytest.mark.asyncio()
async def test_toolkit_init_injects_request_deps_sync() -> None:
    provider = ToolkitProvider()
    sessions: list[UUID] = []
    tool_names: list[str] = []

    @inject
    def get_weather(
        city: str,
        weather: FromDishka[WeatherService],
    ) -> str:
        sessions.append(weather.session.session_id)
        tool_names.append(weather.request.tool_name)
        return weather.forecast(city)

    async with sync_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(
                    name="get_weather",
                    arguments='{"city": "Berlin"}',
                ),
                ToolCallEvent(
                    name="get_weather",
                    arguments='{"city": "Tokyo"}',
                ),
                "All forecasts done.",
            ),
            tools=[Toolkit(get_weather)],
            middleware=[middleware],
        )

        await agent.ask("Weather for Berlin and Tokyo.")

    assert len(sessions) == 2
    assert sessions[0] == sessions[1]
    assert tool_names == ["get_weather", "get_weather"]
