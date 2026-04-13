"""Example: AG2 Toolkit with Dishka-injected tools."""

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from autogen.beta.tools import Toolkit
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)

logger = logging.getLogger(__name__)


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
        self._session = session
        self._request = request

    async def forecast(self, city: str) -> str:
        return (
            f"{city}: sunny "
            f"session={self._session.session_id} "
            f"request={self._request.request_id} "
            f"tool={self._request.tool_name}"
        )


class MyProvider(Provider):
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


toolkit = Toolkit()


@toolkit.tool  # type: ignore[untyped-decorator]
@inject
async def get_weather(
    city: str,
    weather: FromDishka[WeatherService],
) -> str:
    result = await weather.forecast(city)
    logger.info("[toolkit tool] %s", result)
    return result


provider = MyProvider()
container = make_async_container(provider, AG2Provider(), scopes=AG2Scope)

agent = Agent(
    "assistant",
    prompt="Use the weather toolkit.",
    config=TestConfig(
        ToolCallEvent(name="get_weather", arguments='{"city": "Berlin"}'),
        ToolCallEvent(name="get_weather", arguments='{"city": "Tokyo"}'),
        "All forecasts are done.",
    ),
    tools=[
        toolkit,
    ],
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        reply = await agent.ask("Check weather in Berlin and Tokyo.")
        logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
