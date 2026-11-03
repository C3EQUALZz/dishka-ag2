"""Async delegation to a child with sync and async tools."""

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.subagents.common import AppTrace
from tests.integration.subagents.session.common import (
    RequestTrace,
    SessionTrace,
    SubagentProvider,
    ToolObservation,
)


@pytest.mark.asyncio()
async def test_nested_agent_with_mixed_child_tools() -> None:
    provider = SubagentProvider()

    def record(
        stage: str, app: AppTrace, session: SessionTrace, request: RequestTrace
    ) -> None:
        provider.observations.append(
            ToolObservation(
                stage=stage,
                agent_name=session.agent_name,
                app_id=app.app_id,
                session_id=session.session_id,
                request_id=request.request_id,
                request_is_active=request.request_id in provider.active_requests,
            ),
        )

    async with async_env(provider) as (_, middleware):
        child = Agent(
            "child",
            config=TestConfig(
                ToolCallEvent(name="sync_lookup", arguments="{}"),
                ToolCallEvent(name="async_lookup", arguments="{}"),
                "Child finished.",
            ),
            variables={"agent_name": "child"},
            middleware=[middleware],
        )
        parent = Agent(
            "parent",
            config=TestConfig(
                ToolCallEvent(name="ask_child", arguments="{}"),
                "Parent finished.",
            ),
            variables={"agent_name": "parent"},
            middleware=[middleware],
        )

        @child.tool
        @inject
        def sync_lookup(
            app: FromDishka[AppTrace],
            session: FromDishka[SessionTrace],
            request: FromDishka[RequestTrace],
        ) -> str:
            record("sync child", app, session, request)
            return "sync result"

        @child.tool
        @inject
        async def async_lookup(
            app: FromDishka[AppTrace],
            session: FromDishka[SessionTrace],
            request: FromDishka[RequestTrace],
        ) -> str:
            record("async child", app, session, request)
            return "async result"

        @parent.tool
        @inject
        async def ask_child(
            app: FromDishka[AppTrace],
            session: FromDishka[SessionTrace],
            request: FromDishka[RequestTrace],
        ) -> str:
            record("parent before", app, session, request)
            reply = await child.ask("Run both tools.")
            record("parent after", app, session, request)
            return str(reply.body)

        await parent.ask("Ask the child to run both tools.")

    parent_session = provider.sessions["parent"][0]
    child_session = provider.sessions["child"][0]
    parent_request = provider.requests["parent"][0]
    child_requests = provider.requests["child"]
    assert len(provider.sessions["parent"]) == len(provider.sessions["child"]) == 1
    assert parent_session != child_session
    assert len(child_requests) == 2
    assert [request.tool_name for request in child_requests] == [
        "sync_lookup",
        "async_lookup",
    ]
    assert all(request.session_id == child_session for request in child_requests)
    assert (
        len({
            parent_request.request_id,
            *(request.request_id for request in child_requests),
        })
        == 3
    )
    assert [observation.stage for observation in provider.observations] == [
        "parent before",
        "sync child",
        "async child",
        "parent after",
    ]
    assert len({observation.app_id for observation in provider.observations}) == 1
    assert provider.observations[0].request_id == provider.observations[-1].request_id
    assert all(observation.request_is_active for observation in provider.observations)
    assert not provider.active_requests
    assert provider.events.index("session:release:child") < provider.events.index(
        "request:release:parent:ask_child",
    )
