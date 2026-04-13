"""Example: @agent.prompt with Dishka integration.

AG2 builds dynamic prompts before middleware starts the turn, so pass the root
container via Agent(..., dependencies={CONTAINER_NAME: container}). Then
@inject can open REQUEST scope for the prompt function.
"""

import asyncio
import logging

from autogen.beta import Agent, Context
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    CONTAINER_NAME,
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)

logger = logging.getLogger(__name__)


class PromptService:
    async def build(self, context: Context) -> str:
        return (
            "You are a helpful agent. "
            f"The current context variables are {context.variables}."
        )


class MyProvider(Provider):
    @provide(scope=AG2Scope.REQUEST)
    def prompt_service(self) -> PromptService:
        return PromptService()


provider = MyProvider()
container = make_async_container(provider, AG2Provider(), scopes=AG2Scope)

agent = Agent(
    "assistant",
    config=TestConfig("Done."),
    dependencies={
        CONTAINER_NAME: container,
    },
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)


@agent.prompt  # type: ignore[untyped-decorator]
@inject
async def dynamic_sysprompt(
    ctx: Context,
    prompt_service: FromDishka[PromptService],
) -> str:
    prompt = await prompt_service.build(ctx)
    logger.info("[prompt] %s", prompt)
    return prompt


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        reply = await agent.ask(
            "Hello!",
            variables={
                "tenant": "demo",
            },
        )
        logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
