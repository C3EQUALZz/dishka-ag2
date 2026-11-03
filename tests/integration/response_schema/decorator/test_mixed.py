"""Injected response validators alongside sync and async tools."""

import pytest
from ag2 import Agent, PromptedSchema, response_schema
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig
from dishka import AsyncContainer

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.common import REQUEST_DEP_VALUE, AppProvider, RequestDep
from tests.integration.conftest import async_env
from tests.integration.response_schema.common import ParserService, SchemaProvider


@pytest.mark.asyncio()
@pytest.mark.parametrize("validator_kind", ("sync", "async"))
async def test_response_validator_with_mixed_tools(
    app_provider: AppProvider,
    validator_kind: str,
) -> None:
    calls: list[tuple[str, AsyncContainer]] = []

    @response_schema
    @inject
    def sync_validator(
        content: str,
        parser: FromDishka[ParserService],
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> int:
        assert request == REQUEST_DEP_VALUE
        calls.append(("sync validator", container))
        return parser.parse_int(content)

    @response_schema
    @inject
    async def async_validator(
        content: str,
        parser: FromDishka[ParserService],
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> int:
        assert request == REQUEST_DEP_VALUE
        calls.append(("async validator", container))
        return parser.parse_int(content)

    @inject
    def sync_tool(
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> str:
        assert request == REQUEST_DEP_VALUE
        calls.append(("sync tool", container))
        return "ok"

    @inject
    async def async_tool(
        request: FromDishka[RequestDep],
        container: FromDishka[AsyncContainer],
    ) -> str:
        assert request == REQUEST_DEP_VALUE
        calls.append(("async tool", container))
        return "ok"

    validator = sync_validator if validator_kind == "sync" else async_validator
    async with async_env(app_provider, SchemaProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="sync_tool", arguments="{}"),
                ToolCallEvent(name="async_tool", arguments="{}"),
                "43",
            ),
            response_schema=PromptedSchema(validator),
            tools=[sync_tool, async_tool],
            middleware=[middleware],
        )
        reply = await agent.ask("Run both tools and return 43.")
        assert await reply.content() == 43

    assert [name for name, _ in calls] == [
        "sync tool",
        "async tool",
        f"{validator_kind} validator",
    ]
    requests = [container for _, container in calls]
    assert len({id(container) for container in requests}) == 3
    assert all(container.scope is AG2Scope.REQUEST for container in requests)
    assert requests[0].parent_container is requests[1].parent_container
    assert app_provider.request_released.call_count == 3
