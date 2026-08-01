"""Standalone @tool passed via tools=[...] with sync container."""

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig
from ag2.tools import tool

from dishka_ag2 import FromDishka, inject
from tests.common import (
    REQUEST_DEP_VALUE,
    AppProvider,
    RequestDep,
)
from tests.integration.conftest import sync_env


@pytest.mark.asyncio()
async def test_standalone_tool_injects_request_sync(
    app_provider: AppProvider,
) -> None:
    @tool
    @inject
    def greet(
        name: str,
        request_dep: FromDishka[RequestDep],
    ) -> str:
        return str(request_dep)

    async with sync_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(
                    name="greet",
                    arguments='{"name": "Alice"}',
                ),
                "Done.",
            ),
            tools=[greet],
            middleware=[middleware],
        )

        reply = await agent.ask("Greet Alice.")

    assert reply.body is not None
    assert app_provider.request_released.call_count >= 1
    assert str(REQUEST_DEP_VALUE) == "REQUEST"
