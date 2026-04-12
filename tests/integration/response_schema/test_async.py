"""response_schema with Dishka middleware.

Mirrors examples/ag2_response_schema.py — plain validator and injected
validator with APP-scope dependency.
"""

import pytest
from autogen.beta import Agent, PromptedSchema, ResponseSchema, response_schema
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from dishka import Provider, Scope, provide

from dishka_ag2 import FromDishka, inject
from tests.common import APP_DEP_VALUE, REQUEST_DEP_VALUE, AppDep, AppProvider, RequestDep
from tests.integration.conftest import async_env


class ParserService:
    async def parse_int(self, content: str) -> int:
        return int(content.strip())


class SchemaProvider(Provider):
    @provide(scope=Scope.APP)
    def parser(self) -> ParserService:
        return ParserService()


@pytest.mark.asyncio()
async def test_response_schema_plain() -> None:
    @response_schema  # type: ignore[untyped-decorator]
    def parse_int(content: str) -> int:
        return int(content.strip())

    async with async_env(SchemaProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("42"),
            response_schema=PromptedSchema(parse_int),
            middleware=[middleware],
        )

        reply = await agent.ask("Return 42.")
        assert await reply.content() == 42


@pytest.mark.asyncio()
async def test_response_schema_injected_app_scope() -> None:
    @response_schema  # type: ignore[untyped-decorator]
    @inject
    async def parse_int_injected(
        content: str,
        parser: FromDishka[ParserService],
    ) -> int:
        return await parser.parse_int(content)

    async with async_env(SchemaProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("43"),
            response_schema=PromptedSchema(parse_int_injected),
            middleware=[middleware],
        )

        reply = await agent.ask("Return 43.")
        assert await reply.content() == 43


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

        @agent.tool  # type: ignore[untyped-decorator]
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
