"""Integration tests using agent.ask() with TestConfig."""

from collections.abc import Iterable
from typing import NewType
from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.events import BaseEvent, ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from dishka import Provider, Scope, make_async_container, provide

from dishka_autogen import AG2Provider, DishkaMiddleware, FromDishka, inject
from tests.common import (
    APP_DEP_VALUE,
    REQUEST_DEP_VALUE,
    AppDep,
    AppProvider,
    RequestDep,
)

GreetingResult = NewType("GreetingResult", str)


class GreetingProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()
        self.request_released = Mock()

    @provide(scope=Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=Scope.REQUEST)
    def greeting(
        self,
        event: ToolCallEvent,
    ) -> Iterable[GreetingResult]:
        yield GreetingResult(f"Hello from {event.name}")
        self.request_released()


@pytest.mark.asyncio()
async def test_agent_ask_injects_request_deps() -> None:
    greeting_provider = GreetingProvider()
    container = make_async_container(
        greeting_provider,
        AG2Provider(),
    )

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(
                name="greet",
                arguments='{"name": "Alice"}',
            ),
            "Done.",
        ),
        middleware=[Middleware(DishkaMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def greet(
        name: str,
        greeting: FromDishka[GreetingResult],
        mock: FromDishka[Mock],
    ) -> str:
        mock(name, greeting)
        return str(greeting)

    reply = await agent.ask("Greet Alice.")

    greeting_provider.mock.assert_called_once_with(
        "Alice",
        GreetingResult("Hello from greet"),
    )
    greeting_provider.request_released.assert_called_once()
    assert reply.body is not None

    await container.close()


@pytest.mark.asyncio()
async def test_agent_ask_multiple_tool_calls(
    app_provider: AppProvider,
) -> None:
    call_count = 0

    container = make_async_container(AG2Provider(), app_provider)

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="inc", arguments="{}"),
            ToolCallEvent(name="inc", arguments="{}"),
            "All done.",
        ),
        middleware=[Middleware(DishkaMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def inc(
        request_dep: FromDishka[RequestDep],
    ) -> str:
        nonlocal call_count
        call_count += 1
        return str(request_dep)

    await agent.ask("Increment twice.")

    assert call_count == 2

    await container.close()


@pytest.mark.asyncio()
async def test_agent_ask_app_and_request_deps(
    app_provider: AppProvider,
) -> None:
    container = make_async_container(app_provider, AG2Provider())

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(
                name="check",
                arguments="{}",
            ),
            "Done.",
        ),
        middleware=[Middleware(DishkaMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def check(
        app_dep: FromDishka[AppDep],
        request_dep: FromDishka[RequestDep],
        mock: FromDishka[Mock],
    ) -> str:
        mock(app_dep, request_dep)
        return "ok"

    await agent.ask("Check.")

    app_provider.mock.assert_called_once_with(
        APP_DEP_VALUE,
        REQUEST_DEP_VALUE,
    )
    app_provider.request_released.assert_called_once()
    app_provider.app_released.assert_not_called()

    await container.close()
    app_provider.app_released.assert_called_once()


SessionEventDep = NewType("SessionEventDep", str)


class SessionEventProvider(Provider):
    @provide(scope=Scope.SESSION)
    def session_event(
        self,
        event: BaseEvent,
    ) -> SessionEventDep:
        return SessionEventDep(f"turn:{type(event).__name__}")


@pytest.mark.asyncio()
async def test_agent_ask_session_scope_with_base_event() -> None:
    provider = SessionEventProvider()
    container = make_async_container(provider, AG2Provider())

    results: list[str] = []

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="check", arguments="{}"),
            "Done.",
        ),
        middleware=[Middleware(DishkaMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def check(
        session_event: FromDishka[SessionEventDep],
    ) -> str:
        results.append(str(session_event))
        return "ok"

    await agent.ask("Check session.")

    assert len(results) == 1
    assert "turn:" in results[0]

    await container.close()
