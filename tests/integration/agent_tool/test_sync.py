"""@agent.tool with sync Dishka container."""

from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.common import (
    APP_DEP_VALUE,
    REQUEST_DEP_VALUE,
    SESSION_DEP_VALUE,
    AppDep,
    AppProvider,
    RequestDep,
    SessionDep,
)
from tests.integration.conftest import sync_env


@pytest.mark.asyncio()
async def test_agent_tool_injects_all_scopes_sync(
    app_provider: AppProvider,
) -> None:
    async with sync_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="check", arguments="{}"),
                "Done.",
            ),
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        @inject
        def check(
            app_dep: FromDishka[AppDep],
            session_dep: FromDishka[SessionDep],
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(app_dep, session_dep, request_dep)
            return "ok"

        await agent.ask("Check.")

        app_provider.mock.assert_called_once_with(
            APP_DEP_VALUE,
            SESSION_DEP_VALUE,
            REQUEST_DEP_VALUE,
        )
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_agent_tool_multiple_calls_sync(
    app_provider: AppProvider,
) -> None:
    calls = 0

    async with sync_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="inc", arguments="{}"),
                ToolCallEvent(name="inc", arguments="{}"),
                "Done.",
            ),
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        @inject
        def inc(
            request_dep: FromDishka[RequestDep],
        ) -> str:
            nonlocal calls
            calls += 1
            return str(request_dep)

        await agent.ask("Increment twice.")

    assert calls == 2
    assert app_provider.request_released.call_count == 2
