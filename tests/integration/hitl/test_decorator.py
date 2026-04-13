"""@agent.hitl_hook with Dishka DI (decorator form).

Mirrors examples/ag2_standalone_tool_hitl.py.
"""

from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool
from dishka import provide

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.hitl.conftest import AuditLog, BaseHitlProvider


class ConfirmationService:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self.confirmed = False


class HitlProvider(BaseHitlProvider):
    @provide(scope=AG2Scope.REQUEST)
    def confirmation(
        self,
        event: ToolCallEvent,
    ) -> ConfirmationService:
        return ConfirmationService(tool_name=event.name)


@pytest.mark.asyncio()
async def test_hitl_hook_via_decorator() -> None:
    provider = HitlProvider()

    @tool  # type: ignore[untyped-decorator]
    @inject
    async def ask_human(
        context: Context,
        service: FromDishka[ConfirmationService],
    ) -> str:
        answer: str = await context.input("Approve?")
        service.confirmed = True
        return f"{answer} tool={service.tool_name}"

    async with async_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="ask_human", arguments="{}"),
                "Done.",
            ),
            tools=[ask_human],
            middleware=[middleware],
        )

        @agent.hitl_hook  # type: ignore[untyped-decorator]
        @inject
        async def on_human(
            event: HumanInputRequest,
            audit: FromDishka[AuditLog],
            mock: FromDishka[Mock],
        ) -> HumanMessage:
            mock(audit)
            return HumanMessage(content="approved")

        await agent.ask("Request confirmation.")

    provider.mock.assert_called_once_with(AuditLog("asked: Approve?"))
    provider.audit_released.assert_called_once()
