"""hitl_hook= argument form with sync Dishka middleware."""

from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import sync_env
from tests.integration.hitl.common import (
    AuditLog,
    BaseHitlProvider,
    ask_human,
)


@pytest.mark.asyncio()
async def test_hitl_hook_via_argument_sync(
    hitl_provider: BaseHitlProvider,
) -> None:
    @inject
    def on_human(
        event: HumanInputRequest,
        audit: FromDishka[AuditLog],
        mock: FromDishka[Mock],
    ) -> HumanMessage:
        mock(audit)
        return HumanMessage(content="yes")

    async with sync_env(hitl_provider) as (_, middleware):
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

    hitl_provider.mock.assert_called_once_with(AuditLog("asked: Approve?"))
    hitl_provider.audit_released.assert_called_once()
