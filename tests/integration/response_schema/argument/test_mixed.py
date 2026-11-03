"""A response schema alongside sync and async tools."""

import pytest
from ag2 import Agent, PromptedSchema, ResponseSchema
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig
from dishka import AsyncContainer

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.common import APP_DEP_VALUE, REQUEST_DEP_VALUE, AppDep, AppProvider, RequestDep
from tests.integration.conftest import async_env


@pytest.mark.asyncio()
async def test_response_schema_argument_with_mixed_tools(
    app_provider: AppProvider,
) -> None:
    requests: list[AsyncContainer] = []

    @inject
    def sync_tool(
        app: FromDishka[AppDep],
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> str:
        assert app == APP_DEP_VALUE
        assert request == REQUEST_DEP_VALUE
        requests.append(container)
        return "sync result"

    @inject
    async def async_tool(
        app: FromDishka[AppDep],
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> str:
        assert app == APP_DEP_VALUE
        assert request == REQUEST_DEP_VALUE
        requests.append(container)
        return "async result"

    async with async_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="sync_tool", arguments="{}"),
                ToolCallEvent(name="async_tool", arguments="{}"),
                '{"data": 5}',
            ),
            response_schema=PromptedSchema(ResponseSchema(int)),
            tools=[sync_tool, async_tool],
            middleware=[middleware],
        )
        reply = await agent.ask("Run both tools and return 5.")
        assert await reply.content() == 5

    assert len(requests) == 2
    assert requests[0] is not requests[1]
    assert requests[0].parent_container is requests[1].parent_container
    assert all(request.scope is AG2Scope.REQUEST for request in requests)
    assert app_provider.request_released.call_count == 2
