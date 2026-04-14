"""response_schema with sync Dishka middleware."""

import pytest
from autogen.beta import Agent, PromptedSchema, ResponseSchema, response_schema
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.common import APP_DEP_VALUE, REQUEST_DEP_VALUE, AppDep, AppProvider, RequestDep
from tests.integration.conftest import sync_env
from tests.integration.response_schema.common import ParserService, SchemaProvider


@pytest.mark.asyncio()
async def test_response_schema_plain_sync() -> None:
    @response_schema  # type: ignore[untyped-decorator]
    def parse_int(content: str) -> int:
        return int(content.strip())

    async with sync_env(SchemaProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("42"),
            response_schema=PromptedSchema(parse_int),
            middleware=[middleware],
        )

        reply = await agent.ask("Return 42.")
        assert await reply.content() == 42


@pytest.mark.asyncio()
async def test_response_schema_injected_app_scope_sync() -> None:
    @response_schema  # type: ignore[untyped-decorator]
    @inject
    def parse_int_injected(
        content: str,
        parser: FromDishka[ParserService],
    ) -> int:
        return parser.parse_int(content)

    async with sync_env(SchemaProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("43"),
            response_schema=PromptedSchema(parse_int_injected),
            middleware=[middleware],
        )

        reply = await agent.ask("Return 43.")
        assert await reply.content() == 43


@pytest.mark.asyncio()
async def test_response_schema_injected_request_scope_sync(
    app_provider: AppProvider,
) -> None:
    @response_schema  # type: ignore[untyped-decorator]
    @inject
    def parse_int_request(
        content: str,
        request_dep: FromDishka[RequestDep],
    ) -> int:
        assert request_dep == REQUEST_DEP_VALUE
        return int(content.strip())

    async with sync_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("77"),
            response_schema=PromptedSchema(parse_int_request),
            middleware=[middleware],
        )

        reply = await agent.ask("Return 77.")
        assert await reply.content() == 77
        assert app_provider.request_released.call_count >= 1


@pytest.mark.asyncio()
async def test_response_schema_with_tool_injection_sync(
    app_provider: AppProvider,
) -> None:
    ocean_count = ResponseSchema(
        int,
        name="OceanCount",
        description="Number of oceans on Earth.",
    )

    async with sync_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="check", arguments="{}"),
                '{"data": 5}',
            ),
            response_schema=PromptedSchema(ocean_count),
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        @inject
        def check(
            app_dep: FromDishka[AppDep],
            request_dep: FromDishka[RequestDep],
        ) -> str:
            assert app_dep == APP_DEP_VALUE
            assert request_dep == REQUEST_DEP_VALUE
            return "ok"

        reply = await agent.ask("How many oceans?")
        assert await reply.content() == 5
