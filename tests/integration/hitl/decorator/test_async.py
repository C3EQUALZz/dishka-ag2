"""@agent.hitl_hook with async Dishka middleware."""

from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.hitl.common import (
    AuditLog,
    ConfirmationService,
    HitlProvider,
)


@pytest.mark.asyncio()
async def test_hitl_hook_via_decorator() -> None:
    provider = HitlProvider()

    @tool
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

        @agent.hitl_hook
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
