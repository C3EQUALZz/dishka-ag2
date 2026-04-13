"""Example: nested AG2 agents sharing a CONVERSATION scope via Dishka.

The caller opens ``container(scope=AG2Scope.CONVERSATION)`` natively and
passes the resulting container to every ``Agent.ask()`` via
``dependencies={CONTAINER_NAME: conv}``. The parent tool receives the same
conversation container as a Dishka dependency and forwards it to the nested
``child_agent.ask()`` so parent and child share ``ConversationTrace``. SESSION
stays per-``Agent.ask()`` and REQUEST stays per tool call.
"""

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    CONTAINER_NAME,
    AG2Provider,
    AG2Scope,
    ConversationAsyncContainer,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConversationTrace:
    conversation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class SessionTrace:
    agent_name: str
    conversation_id: UUID
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RequestTrace:
    agent_name: str
    tool_name: str
    conversation_id: UUID
    session_id: UUID
    request_id: UUID = field(default_factory=uuid4)


class TraceProvider(Provider):
    @provide(scope=AG2Scope.CONVERSATION)
    def conversation_trace(self) -> Iterable[ConversationTrace]:
        trace = ConversationTrace()
        logger.info("[conversation] created: conversation=%s", trace.conversation_id)
        yield trace
        logger.info("[conversation] released: conversation=%s", trace.conversation_id)

    @provide(scope=AG2Scope.SESSION)
    def session_trace(
        self,
        context: Context,
        conversation: ConversationTrace,
    ) -> Iterable[SessionTrace]:
        trace = SessionTrace(
            agent_name=str(context.variables["agent_name"]),
            conversation_id=conversation.conversation_id,
        )
        logger.info(
            "[session] created: agent=%s conversation=%s session=%s",
            trace.agent_name,
            trace.conversation_id,
            trace.session_id,
        )
        yield trace
        logger.info(
            "[session] released: agent=%s conversation=%s session=%s",
            trace.agent_name,
            trace.conversation_id,
            trace.session_id,
        )

    @provide(scope=AG2Scope.REQUEST)
    def request_trace(
        self,
        event: ToolCallEvent,
        session: SessionTrace,
    ) -> Iterable[RequestTrace]:
        trace = RequestTrace(
            agent_name=session.agent_name,
            tool_name=event.name,
            conversation_id=session.conversation_id,
            session_id=session.session_id,
        )
        logger.info(
            "[request] created: agent=%s tool=%s conversation=%s session=%s request=%s",
            trace.agent_name,
            trace.tool_name,
            trace.conversation_id,
            trace.session_id,
            trace.request_id,
        )
        yield trace
        logger.info(
            "[request] released: agent=%s tool=%s conversation=%s session=%s request=%s",
            trace.agent_name,
            trace.tool_name,
            trace.conversation_id,
            trace.session_id,
            trace.request_id,
        )


provider = TraceProvider()
container = make_async_container(
    provider,
    AG2Provider(),
    scopes=AG2Scope,
)
middleware = Middleware(DishkaAsyncMiddleware, container=container)

child_agent = Agent(
    "child",
    prompt="You are a child agent. Use child_lookup.",
    config=TestConfig(
        ToolCallEvent(name="child_lookup", arguments='{"topic": "scopes"}'),
        "Child finished.",
    ),
    middleware=[middleware],
    variables={"agent_name": "child"},
)

parent_agent = Agent(
    "parent",
    prompt="You are a parent agent. Use ask_child.",
    config=TestConfig(
        ToolCallEvent(name="ask_child", arguments='{"question": "Check scopes"}'),
        "Parent finished.",
    ),
    middleware=[middleware],
    variables={"agent_name": "parent"},
)


@child_agent.tool  # type: ignore[untyped-decorator]
@inject
async def child_lookup(  # noqa: RUF029
    topic: str,
    conversation: FromDishka[ConversationTrace],
    session: FromDishka[SessionTrace],
    request: FromDishka[RequestTrace],
) -> str:
    logger.info(
        "[child-tool] topic=%s conversation=%s session=%s request=%s",
        topic,
        conversation.conversation_id,
        session.session_id,
        request.request_id,
    )
    return (
        f"child saw conversation={conversation.conversation_id} "
        f"session={session.session_id} request={request.request_id}"
    )


@parent_agent.tool  # type: ignore[untyped-decorator]
@inject
async def ask_child(
    question: str,
    conversation_container: FromDishka[ConversationAsyncContainer],
    conversation: FromDishka[ConversationTrace],
    session: FromDishka[SessionTrace],
    request: FromDishka[RequestTrace],
) -> str:
    logger.info(
        "[parent-tool] before child: question=%s conversation=%s session=%s request=%s",
        question,
        conversation.conversation_id,
        session.session_id,
        request.request_id,
    )
    reply = await child_agent.ask(
        "Inspect the current DI scopes.",
        dependencies={CONTAINER_NAME: conversation_container},
    )
    logger.info(
        "[parent-tool] after child: conversation=%s session=%s child_reply=%s",
        conversation.conversation_id,
        session.session_id,
        reply.body,
    )
    return f"child replied: {reply.body}"


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        async with container(scope=AG2Scope.CONVERSATION) as conv:
            reply = await parent_agent.ask(
                "Ask the child agent to inspect scopes.",
                dependencies={CONTAINER_NAME: conv},
            )
            logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
