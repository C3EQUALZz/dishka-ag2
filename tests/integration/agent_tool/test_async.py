"""@agent.tool with async Dishka container.

Mirrors examples/ag2_agent_tool.py — APP, SESSION and REQUEST scopes.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import NewType
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from dishka import Provider, Scope, provide

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
from tests.integration.conftest import async_env


@dataclass(frozen=True)
class ConversationState:
    conversation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolRequestState:
    tool_name: str
    request_id: UUID = field(default_factory=uuid4)


Greeting = NewType("Greeting", str)


class AgentToolProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()

    @provide(scope=Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=Scope.SESSION)
    def conversation(self) -> ConversationState:
        return ConversationState()

    @provide(scope=Scope.REQUEST)
    def tool_request(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)

    @provide(scope=Scope.REQUEST)
    def greeting(
        self,
        conversation: ConversationState,
        request: ToolRequestState,
    ) -> Iterable[Greeting]:
        yield Greeting(
            f"hi cid={conversation.conversation_id} "
            f"rid={request.request_id} tool={request.tool_name}",
        )


@pytest.mark.asyncio()
async def test_agent_tool_injects_all_scopes(
    app_provider: AppProvider,
) -> None:
    async with async_env(app_provider) as (_, middleware):
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
        async def check(
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
async def test_agent_tool_request_scope_per_call() -> None:
    provider = AgentToolProvider()
    requests: list[UUID] = []

    async with async_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="greet", arguments='{"name": "A"}'),
                ToolCallEvent(name="greet", arguments='{"name": "B"}'),
                "All done.",
            ),
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        @inject
        async def greet(
            name: str,
            greeting: FromDishka[Greeting],
            request: FromDishka[ToolRequestState],
        ) -> str:
            requests.append(request.request_id)
            return str(greeting)

        await agent.ask("Greet two.")

    assert len(requests) == 2
    assert requests[0] != requests[1]


@pytest.mark.asyncio()
async def test_agent_tool_session_state_shared_across_calls() -> None:
    provider = AgentToolProvider()
    conversations: list[UUID] = []

    async with async_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="visit", arguments="{}"),
                ToolCallEvent(name="visit", arguments="{}"),
                "Done.",
            ),
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        @inject
        async def visit(
            conversation: FromDishka[ConversationState],
        ) -> str:
            conversations.append(conversation.conversation_id)
            return "ok"

        await agent.ask("Visit twice.")

    assert len(conversations) == 2
    assert conversations[0] == conversations[1]
