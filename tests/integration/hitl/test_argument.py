"""hitl_hook= argument form with Dishka DI.

Mirrors examples/ag2_standalone_tool_hitl_arg.py.
"""

from unittest.mock import Mock

import pytest
from autogen.beta import Agent
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.hitl.conftest import (
    AuditLog,
    BaseHitlProvider,
    ask_human,
)


@pytest.mark.asyncio()
async def test_hitl_hook_via_argument(
    hitl_provider: BaseHitlProvider,
) -> None:
    @inject
    async def on_human(
        event: HumanInputRequest,
        audit: FromDishka[AuditLog],
        mock: FromDishka[Mock],
    ) -> HumanMessage:
        mock(audit)
        return HumanMessage(content="yes")

    async with async_env(hitl_provider) as (_, middleware):
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
