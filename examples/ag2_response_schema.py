"""Example: response_schema with Dishka middleware.

Demonstrates PromptedSchema validators with injected REQUEST dependencies.
"""

import asyncio
import logging

from autogen.beta import Agent, PromptedSchema, response_schema
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)

logger = logging.getLogger(__name__)


class ParserService:
    async def parse_int(self, content: str) -> int:
        return int(content.strip())


class MyProvider(Provider):
    @provide(scope=AG2Scope.REQUEST)
    def parser_service(self) -> ParserService:
        return ParserService()


@response_schema  # type: ignore[untyped-decorator]
def parse_int(content: str) -> int:
    return int(content.strip())


@response_schema  # type: ignore[untyped-decorator]
@inject
async def parse_int_with_dishka(
    content: str,
    parser: FromDishka[ParserService],
) -> int:
    return await parser.parse_int(content)


provider = MyProvider()
container = make_async_container(provider, AG2Provider(), scopes=AG2Scope)

plain_schema_agent = Agent(
    "plain_schema_agent",
    config=TestConfig("42"),
    response_schema=PromptedSchema(parse_int),
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)

injected_schema_agent = Agent(
    "injected_schema_agent",
    config=TestConfig("43"),
    response_schema=PromptedSchema(parse_int_with_dishka),
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        plain_reply = await plain_schema_agent.ask("Return 42.")
        logger.info("[plain response_schema] %s", await plain_reply.content())

        injected_reply = await injected_schema_agent.ask("Return 43.")
        logger.info("[injected response_schema] %s", await injected_reply.content())
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
