"""Standalone @tool passed via tools=[...] with sync container."""

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool

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
    @tool  # type: ignore[untyped-decorator]
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
