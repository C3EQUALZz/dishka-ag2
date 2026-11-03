"""Sync and async tools sharing an async Dishka container."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from threading import get_ident

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig
from dishka import Provider, provide

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.common import APP_DEP_VALUE, AppDep, AppProvider
from tests.integration.conftest import async_env
from tests.integration.scope_state import SessionState


@dataclass
class RequestResource:
    active: bool = True


class MixedToolsProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.closed: list[RequestResource] = []
        self.lifecycle_threads: list[int] = []

    @provide(scope=AG2Scope.SESSION)
    def session(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    async def resource(self) -> AsyncIterator[RequestResource]:
        await asyncio.sleep(0)
        resource = RequestResource()
        self.lifecycle_threads.append(get_ident())
        try:
            yield resource
        finally:
            resource.active = False
            self.closed.append(resource)
            self.lifecycle_threads.append(get_ident())


@pytest.mark.asyncio()
async def test_mixed_tools_resolve_dependencies_from_async_container(
    app_provider: AppProvider,
) -> None:
    provider = MixedToolsProvider()
    loop_thread = get_ident()
    calls: dict[str, tuple[AppDep, SessionState, RequestResource, int]] = {}

    async with async_env(app_provider, provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="sync_tool", arguments="{}"),
                ToolCallEvent(name="async_tool", arguments="{}"),
                "Done.",
            ),
            middleware=[middleware],
        )

        @agent.tool
        @inject
        def sync_tool(
            app: FromDishka[AppDep],
            session: FromDishka[SessionState],
            resource: FromDishka[RequestResource],
        ) -> str:
            assert resource.active
            calls["sync"] = (app, session, resource, get_ident())
            return "sync"

        @agent.tool
        @inject
        async def async_tool(
            app: FromDishka[AppDep],
            session: FromDishka[SessionState],
            resource: FromDishka[RequestResource],
        ) -> str:
            assert resource.active
            calls["async"] = (app, session, resource, get_ident())
            return "async"

        await agent.ask("Run both tools.")

    assert calls.keys() == {"sync", "async"}
    sync_app, sync_session, sync_resource, sync_thread = calls["sync"]
    async_app, async_session, async_resource, async_thread = calls["async"]
    assert sync_app == async_app == APP_DEP_VALUE
    assert sync_session is async_session
    assert sync_resource is not async_resource
    assert provider.closed == [sync_resource, async_resource]
    assert not sync_resource.active
    assert not async_resource.active
    assert sync_thread != loop_thread
    assert async_thread == loop_thread
    assert provider.lifecycle_threads == [loop_thread] * 4
