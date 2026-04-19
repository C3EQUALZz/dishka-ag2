"""Agent.ask() calls with sync container and separate SESSION/REQUEST scopes."""

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import sync_env
from tests.integration.subagents.common import AppTrace
from tests.integration.subagents.session.common import (
    RequestTrace,
    SessionTrace,
    SubagentProvider,
    ToolObservation,
)


@pytest.mark.asyncio()
async def test_agent_asks_use_separate_session_and_request_sync() -> None:
    provider = SubagentProvider()

    async with sync_env(provider) as (_, middleware):
        parent_agent = Agent(
            "parent",
            config=TestConfig(
                ToolCallEvent(
                    name="parent_lookup",
                    arguments='{"topic": "parent"}',
                ),
                "Parent finished.",
            ),
            middleware=[middleware],
            variables={"agent_name": "parent"},
        )
        child_agent = Agent(
            "child",
            config=TestConfig(
                ToolCallEvent(
                    name="child_lookup",
                    arguments='{"topic": "child"}',
                ),
                "Child finished.",
            ),
            middleware=[middleware],
            variables={"agent_name": "child"},
        )

        @parent_agent.tool
        @inject
        def parent_lookup(
            topic: str,
            app: FromDishka[AppTrace],
            session: FromDishka[SessionTrace],
            request: FromDishka[RequestTrace],
        ) -> str:
            provider.events.append("tool:parent")
            provider.observations.append(
                ToolObservation(
                    stage=f"parent:{topic}",
                    agent_name=session.agent_name,
                    app_id=app.app_id,
                    session_id=session.session_id,
                    request_id=request.request_id,
                    request_is_active=request.request_id in provider.active_requests,
                ),
            )
            return "parent ok"

        @child_agent.tool
        @inject
        def child_lookup(
            topic: str,
            app: FromDishka[AppTrace],
            session: FromDishka[SessionTrace],
            request: FromDishka[RequestTrace],
        ) -> str:
            provider.events.append("tool:child")
            provider.observations.append(
                ToolObservation(
                    stage=f"child:{topic}",
                    agent_name=session.agent_name,
                    app_id=app.app_id,
                    session_id=session.session_id,
                    request_id=request.request_id,
                    request_is_active=request.request_id in provider.active_requests,
                ),
            )
            return "child ok"

        await parent_agent.ask("Run parent.")
        await child_agent.ask("Run child.")

    parent_session = provider.sessions["parent"][0]
    child_session = provider.sessions["child"][0]
    parent_request = provider.requests["parent"][0]
    child_request = provider.requests["child"][0]

    assert parent_session != child_session
    assert parent_request.session_id == parent_session
    assert child_request.session_id == child_session
    assert parent_request.request_id != child_request.request_id
    assert parent_request.tool_name == "parent_lookup"
    assert child_request.tool_name == "child_lookup"

    assert {observation.app_id for observation in provider.observations} == {
        provider._app.app_id,  # noqa: SLF001
    }
    assert [observation.agent_name for observation in provider.observations] == [
        "parent",
        "child",
    ]
    assert [observation.session_id for observation in provider.observations] == [
        parent_session,
        child_session,
    ]
    assert [observation.request_id for observation in provider.observations] == [
        parent_request.request_id,
        child_request.request_id,
    ]
    assert all(observation.request_is_active for observation in provider.observations)

    assert provider.events == [
        "session:create:parent",
        "request:create:parent:parent_lookup",
        "tool:parent",
        "request:release:parent:parent_lookup",
        "session:release:parent",
        "session:create:child",
        "request:create:child:child_lookup",
        "tool:child",
        "request:release:child:child_lookup",
        "session:release:child",
    ]
