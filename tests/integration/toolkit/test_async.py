"""AG2 Toolkit with injected tools, async container.

Mirrors examples/ag2_toolkit.py.
"""

from dataclasses import dataclass, field
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import Toolkit
from dishka import Provider, provide

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.integration.conftest import async_env


@dataclass(frozen=True)
class SessionState:
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolRequestState:
    tool_name: str
    request_id: UUID = field(default_factory=uuid4)


class WeatherService:
    def __init__(
        self,
        session: SessionState,
        request: ToolRequestState,
    ) -> None:
        self.session = session
        self.request = request

    async def forecast(self, city: str) -> str:
        return f"{city}:sunny tool={self.request.tool_name}"


class ToolkitProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()

    @provide(scope=AG2Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=AG2Scope.SESSION)
    def session_state(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)

    @provide(scope=AG2Scope.REQUEST)
    def weather_service(
        self,
        session: SessionState,
        request: ToolRequestState,
    ) -> WeatherService:
        return WeatherService(session=session, request=request)


@pytest.mark.asyncio()
async def test_toolkit_injects_request_deps() -> None:
    provider = ToolkitProvider()
    sessions: list[UUID] = []
    tool_names: list[str] = []

    toolkit = Toolkit()

    @toolkit.tool  # type: ignore[untyped-decorator]
    @inject
    async def get_weather(
        city: str,
        weather: FromDishka[WeatherService],
    ) -> str:
        sessions.append(weather.session.session_id)
        tool_names.append(weather.request.tool_name)
        return await weather.forecast(city)

    async with async_env(provider) as (_, middleware):
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
            tools=[toolkit],
            middleware=[middleware],
        )

        await agent.ask("Weather for Berlin and Tokyo.")

    assert len(sessions) == 2
    assert sessions[0] == sessions[1]
    assert tool_names == ["get_weather", "get_weather"]
