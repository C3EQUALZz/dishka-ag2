"""@response_schema with async Dishka middleware."""

import pytest
from autogen.beta import Agent, PromptedSchema, response_schema
from autogen.beta.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.common import REQUEST_DEP_VALUE, AppProvider, RequestDep
from tests.integration.conftest import async_env
from tests.integration.response_schema.common import ParserService, SchemaProvider


@pytest.mark.asyncio()
async def test_response_schema_plain() -> None:
    @response_schema
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
    @response_schema
    @inject
    async def parse_int_injected(
        content: str,
        parser: FromDishka[ParserService],
    ) -> int:
        return parser.parse_int(content)

    async with async_env(SchemaProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("43"),
            response_schema=PromptedSchema(parse_int_injected),
            middleware=[middleware],
        )

        reply = await agent.ask("Return 43.")
        content = await reply.content()
        assert content == 43  # type: ignore[comparison-overlap]


@pytest.mark.asyncio()
async def test_response_schema_injected_request_scope(
    app_provider: AppProvider,
) -> None:
    @response_schema
    @inject
    async def parse_int_request(
        content: str,
        request_dep: FromDishka[RequestDep],
    ) -> int:
        assert request_dep == REQUEST_DEP_VALUE
        return int(content.strip())

    async with async_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("77"),
            response_schema=PromptedSchema(parse_int_request),
            middleware=[middleware],
        )

        reply = await agent.ask("Return 77.")
        content = await reply.content()
        assert content == 77  # type: ignore[comparison-overlap]
        assert app_provider.request_released.call_count >= 1
