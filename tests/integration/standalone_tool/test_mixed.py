"""Standalone sync and async tools with an async container."""

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig
from ag2.tools import tool
from dishka import AsyncContainer

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.common import (
    APP_DEP_VALUE,
    REQUEST_DEP_VALUE,
    SESSION_DEP_VALUE,
    AppDep,
    AppProvider,
    RequestDep,
    SessionDep,
)
from tests.integration.conftest import async_env


@pytest.mark.asyncio()
async def test_standalone_mixed_tools(app_provider: AppProvider) -> None:
    calls: list[tuple[str, AsyncContainer]] = []

    @tool
    @inject
    def sync_tool(
        app: FromDishka[AppDep],
        session: FromDishka[SessionDep],
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> str:
        assert (app, session, request) == (
            APP_DEP_VALUE,
            SESSION_DEP_VALUE,
            REQUEST_DEP_VALUE,
        )
        calls.append(("sync", container))
        return "sync result"

    @tool
    @inject
    async def async_tool(
        app: FromDishka[AppDep],
        session: FromDishka[SessionDep],
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> str:
        assert (app, session, request) == (
            APP_DEP_VALUE,
            SESSION_DEP_VALUE,
            REQUEST_DEP_VALUE,
        )
        calls.append(("async", container))
        return "async result"

    async with async_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="sync_tool", arguments="{}"),
                ToolCallEvent(name="async_tool", arguments="{}"),
                "Done.",
            ),
            tools=[sync_tool, async_tool],
            middleware=[middleware],
        )
        await agent.ask("Run both tools.")

    assert [name for name, _ in calls] == ["sync", "async"]
    sync_request, async_request = (container for _, container in calls)
    assert sync_request.scope is async_request.scope is AG2Scope.REQUEST
    assert sync_request is not async_request
    assert sync_request.parent_container is async_request.parent_container
    assert sync_request.parent_container is not None
    assert sync_request.parent_container.scope is AG2Scope.SESSION
    assert app_provider.request_released.call_count == 2
    app_provider.session_released.assert_called_once()
