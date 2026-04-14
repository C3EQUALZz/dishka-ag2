"""@agent.hitl_hook with sync Dishka middleware."""

from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import sync_env
from tests.integration.hitl.common import AuditLog, HitlProvider, ask_human


@pytest.mark.asyncio()
async def test_hitl_hook_via_decorator_sync() -> None:
    provider = HitlProvider()

    async with sync_env(provider) as (_, middleware):
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
        def on_human(
            event: HumanInputRequest,
            audit: FromDishka[AuditLog],
            mock: FromDishka[Mock],
        ) -> HumanMessage:
            mock(audit)
            return HumanMessage(content="approved")

        await agent.ask("Request confirmation.")

    provider.mock.assert_called_once_with(AuditLog("asked: Approve?"))
    provider.audit_released.assert_called_once()
