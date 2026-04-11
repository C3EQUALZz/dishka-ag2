import asyncio
import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from dishka import Provider, Scope, make_async_container, provide

from dishka_ag2 import AG2Provider, DishkaAsyncMiddleware, FromDishka, inject

logger = logging.getLogger(__name__)


class AppCounter:
    def __init__(self) -> None:
        self._value = 0

    def increment(self) -> int:
        self._value += 1
        return self._value


@dataclass(frozen=True)
class ConversationState:
    conversation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolRequestState:
    tool_name: str
    request_id: UUID = field(default_factory=uuid4)


class GreetingService:
    def __init__(
        self,
        conversation: ConversationState,
        request: ToolRequestState,
    ) -> None:
        self._conversation = conversation
        self._request = request

    async def greet(self, name: str) -> str:
        return (
            f"Hello, {name}! "
            f"conversation_id={self._conversation.conversation_id} "
            f"request_id={self._request.request_id} "
            f"tool={self._request.tool_name}"
        )


class MyProvider(Provider):
    @provide(scope=Scope.APP)
    def app_counter(self) -> AppCounter:
        return AppCounter()

    @provide(scope=Scope.SESSION)
    def conversation_state(self) -> ConversationState:
        return ConversationState()

    @provide(scope=Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)

    @provide(scope=Scope.REQUEST)
    def greeting_service(
        self,
        conversation: ConversationState,
        request: ToolRequestState,
    ) -> GreetingService:
        return GreetingService(conversation=conversation, request=request)


provider = MyProvider()
container = make_async_container(provider, AG2Provider())

agent = Agent(
    "assistant",
    prompt="Use tools to greet users.",
    config=TestConfig(
        ToolCallEvent(name="greet_user", arguments='{"name": "Connor"}'),
        ToolCallEvent(name="greet_user", arguments='{"name": "Sara"}'),
        "All greetings are done.",
    ),
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)


@agent.tool
@inject
async def greet_user(
    name: str,
    greeting: FromDishka[GreetingService],
    counter: FromDishka[AppCounter],
) -> str:
    count = counter.increment()
    result = await greeting.greet(name)
    logger.info("[tool] count=%s %s", count, result)
    return result


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        reply = await agent.ask("Greet Connor and Sara.")
        logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
