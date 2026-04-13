"""Example: nested AG2 agents and Dishka scope lifecycle.

The parent agent calls a child agent from a tool. The logs show that each
Agent.ask() gets its own SESSION scope by default, while every tool call gets
its own REQUEST scope.
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
from dishka import Provider, Scope, make_async_container, provide

from dishka_ag2 import AG2Provider, DishkaAsyncMiddleware, FromDishka, inject

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionTrace:
    agent_name: str
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RequestTrace:
    agent_name: str
    tool_name: str
    session_id: UUID
    request_id: UUID = field(default_factory=uuid4)


class TraceProvider(Provider):
    @provide(scope=Scope.SESSION)
    def session_trace(self, context: Context) -> Iterable[SessionTrace]:
        trace = SessionTrace(agent_name=str(context.variables["agent_name"]))
        logger.info(
            "[session] created: agent=%s session=%s",
            trace.agent_name,
            trace.session_id,
        )
        yield trace
        logger.info(
            "[session] released: agent=%s session=%s",
            trace.agent_name,
            trace.session_id,
        )

    @provide(scope=Scope.REQUEST)
    def request_trace(
        self,
        event: ToolCallEvent,
        session: SessionTrace,
    ) -> Iterable[RequestTrace]:
        trace = RequestTrace(
            agent_name=session.agent_name,
            tool_name=event.name,
            session_id=session.session_id,
        )
        logger.info(
            "[request] created: agent=%s tool=%s session=%s request=%s",
            trace.agent_name,
            trace.tool_name,
            trace.session_id,
            trace.request_id,
        )
        yield trace
        logger.info(
            "[request] released: agent=%s tool=%s session=%s request=%s",
            trace.agent_name,
            trace.tool_name,
            trace.session_id,
            trace.request_id,
        )


provider = TraceProvider()
container = make_async_container(provider, AG2Provider())
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
    session: FromDishka[SessionTrace],
    request: FromDishka[RequestTrace],
) -> str:
    logger.info(
        "[child-tool] topic=%s session=%s request=%s",
        topic,
        session.session_id,
        request.request_id,
    )
    return f"child saw session={session.session_id} request={request.request_id}"


@parent_agent.tool  # type: ignore[untyped-decorator]
@inject
async def ask_child(
    question: str,
    session: FromDishka[SessionTrace],
    request: FromDishka[RequestTrace],
) -> str:
    logger.info(
        "[parent-tool] before child: question=%s session=%s request=%s",
        question,
        session.session_id,
        request.request_id,
    )
    reply = await child_agent.ask("Inspect the current DI scopes.")
    logger.info(
        "[parent-tool] after child: session=%s request=%s child_reply=%s",
        session.session_id,
        request.request_id,
        reply.body,
    )
    return f"child replied: {reply.body}"


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        reply = await parent_agent.ask("Ask the child agent to inspect scopes.")
        logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
