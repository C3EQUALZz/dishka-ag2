"""hitl_hook= argument form with Dishka DI.

Mirrors examples/ag2_standalone_tool_hitl_arg.py.
"""

from collections.abc import Iterable
from typing import NewType
from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool
from dishka import Provider, Scope, provide

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import async_env

AuditLog = NewType("AuditLog", str)


class ArgHitlProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()

    @provide(scope=Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=Scope.REQUEST)
    def audit(
        self,
        event: HumanInputRequest,
    ) -> Iterable[AuditLog]:
        yield AuditLog(f"asked: {event.content}")


@pytest.mark.asyncio()
async def test_hitl_hook_via_argument() -> None:
    provider = ArgHitlProvider()

    @tool  # type: ignore[untyped-decorator]
    async def ask_human(context: Context) -> str:
        answer: str = await context.input("Confirm?")
        return answer

    @inject
    async def on_human(
        event: HumanInputRequest,
        audit: FromDishka[AuditLog],
        mock: FromDishka[Mock],
    ) -> HumanMessage:
        mock(audit)
        return HumanMessage(content="yes")

    async with async_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="ask_human", arguments="{}"),
                "Done.",
            ),
            tools=[ask_human],
            hitl_hook=on_human,
            middleware=[middleware],
        )

        await agent.ask("Please confirm.")

    provider.mock.assert_called_once_with(AuditLog("asked: Confirm?"))
