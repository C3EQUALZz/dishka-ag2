"""Example: REQUEST scope on LLM calls via on_llm_call hook.

Demonstrates that each LLM call gets its own REQUEST-scoped container,
while SESSION-scoped dependencies are shared across the turn.

Uses standalone @tool decorator and tools= parameter on Agent.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool
from dishka import Provider, Scope, make_async_container, provide

from dishka_ag2 import AG2Provider, DishkaAsyncMiddleware, FromDishka, inject

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionTracker:
    session_id: UUID = field(default_factory=uuid4)


class LLMCallCounter:
    def __init__(self) -> None:
        self._count = 0

    def increment(self) -> int:
        self._count += 1
        return self._count


class MyProvider(Provider):
    @provide(scope=Scope.APP)
    def llm_call_counter(self) -> LLMCallCounter:
        return LLMCallCounter()

    @provide(scope=Scope.SESSION)
    def session_tracker(self) -> SessionTracker:
        return SessionTracker()


@tool
@inject
async def greet_user(
    name: str,
    session: FromDishka[SessionTracker],
    counter: FromDishka[LLMCallCounter],
) -> str:
    count = counter.increment()
    result = f"Hello {name}! session={session.session_id} call_count={count}"
    logger.info("[tool] %s", result)
    return result


provider = MyProvider()
container = make_async_container(provider, AG2Provider())

agent = Agent(
    "assistant",
    prompt="Use tools to greet users.",
    config=TestConfig(
        ToolCallEvent(name="greet_user", arguments='{"name": "Alice"}'),
        ToolCallEvent(name="greet_user", arguments='{"name": "Bob"}'),
        "All greetings done.",
    ),
    tools=[greet_user],
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        reply = await agent.ask("Greet Alice and Bob.")
        logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
