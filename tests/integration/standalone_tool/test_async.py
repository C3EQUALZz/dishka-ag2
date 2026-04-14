"""Standalone @tool passed via tools=[...] with async container.

Mirrors examples/ag2_standalone_tool.py — REQUEST-scope per LLM call and
SESSION-scope shared across the turn.
"""

from typing import TYPE_CHECKING, NewType
from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool
from dishka import Provider, provide

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.scope_state import SessionState

if TYPE_CHECKING:
    from uuid import UUID

LLMCounter = NewType("LLMCounter", int)


class StandaloneProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self._count = 0
        self.mock = Mock()

    @provide(scope=AG2Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=AG2Scope.SESSION)
    def session_tracker(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    def counter(self) -> LLMCounter:
        self._count += 1
        return LLMCounter(self._count)


@pytest.mark.asyncio()
async def test_standalone_tool_injects_session_and_request() -> None:
    provider = StandaloneProvider()
    sessions: list[UUID] = []
    counters: list[int] = []

    @tool  # type: ignore[untyped-decorator]
    @inject
    async def greet(
        name: str,
        session: FromDishka[SessionState],
        counter: FromDishka[LLMCounter],
    ) -> str:
        sessions.append(session.session_id)
        counters.append(int(counter))
        return f"Hello {name}"

    async with async_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="greet", arguments='{"name": "Alice"}'),
                ToolCallEvent(name="greet", arguments='{"name": "Bob"}'),
                "All greetings done.",
            ),
            tools=[greet],
            middleware=[middleware],
        )

        await agent.ask("Greet Alice and Bob.")

    assert len(sessions) == 2
    assert sessions[0] == sessions[1]
    assert len(counters) == 2
    assert counters[0] != counters[1]
