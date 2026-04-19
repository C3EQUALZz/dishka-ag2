"""Agent(..., response_schema=...) with async Dishka middleware."""

import pytest
from autogen.beta import Agent, PromptedSchema, ResponseSchema
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.common import APP_DEP_VALUE, REQUEST_DEP_VALUE, AppDep, AppProvider, RequestDep
from tests.integration.conftest import async_env


@pytest.mark.asyncio()
async def test_response_schema_with_tool_injection(
    app_provider: AppProvider,
) -> None:
    ocean_count = ResponseSchema(
        int,
        name="OceanCount",
        description="Number of oceans on Earth.",
    )

    async with async_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="check", arguments="{}"),
                '{"data": 5}',
            ),
            response_schema=PromptedSchema(ocean_count),
            middleware=[middleware],
        )

        @agent.tool
        @inject
        async def check(
            app_dep: FromDishka[AppDep],
            request_dep: FromDishka[RequestDep],
        ) -> str:
            assert app_dep == APP_DEP_VALUE
            assert request_dep == REQUEST_DEP_VALUE
            return "ok"

        reply = await agent.ask("How many oceans?")
        assert await reply.content() == 5
