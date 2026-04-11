"""Example: HITL (Human-In-The-Loop) with Dishka DI.

Demonstrates two ways to register hitl_hook with @inject:
  1. hitl_hook= argument on Agent
  2. @agent.hitl_hook decorator

The on_human_input middleware hook creates a REQUEST-scoped container,
making HumanInputRequest available for injection in providers and hitl_hook.
"""

import asyncio
import logging
from collections.abc import Iterable
from typing import NewType

from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool
from dishka import Provider, Scope, make_async_container, provide

from dishka_ag2 import AG2Provider, DishkaAsyncMiddleware, FromDishka, inject

logger = logging.getLogger(__name__)


AuditLog = NewType("AuditLog", str)


class AuditProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def audit_log(
        self,
        event: HumanInputRequest,
    ) -> Iterable[AuditLog]:
        log_entry = AuditLog(f"Human was asked: {event.content}")
        logger.info("[audit] created: %s", log_entry)
        yield log_entry
        logger.info("[audit] released: %s", log_entry)


class ConfirmationService:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self.confirmed = False


class ToolProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def confirmation_service(
        self,
        event: ToolCallEvent,
    ) -> ConfirmationService:
        return ConfirmationService(tool_name=event.name)


@tool
@inject
async def ask_human(
    context: Context,
    service: FromDishka[ConfirmationService],
) -> str:
    """Pauses agent execution to await human confirmation."""
    answer = await context.input("Please provide confirmation:")
    service.confirmed = True
    logger.info(
        "[tool] human said: %s, tool=%s, confirmed=%s",
        answer,
        service.tool_name,
        service.confirmed,
    )
    return f"Human said: {answer}"


provider_audit = AuditProvider()
provider_tool = ToolProvider()
container = make_async_container(
    provider_audit,
    provider_tool,
    AG2Provider(),
)

agent = Agent(
    "assistant",
    prompt="Use ask_human when you need confirmation.",
    config=TestConfig(
        ToolCallEvent(name="ask_human", arguments="{}"),
        "Confirmation received.",
    ),
    tools=[ask_human],
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)


@agent.hitl_hook
@inject
async def on_human_input(
    event: HumanInputRequest,
    audit: FromDishka[AuditLog],
) -> HumanMessage:
    """HITL hook with injected audit dependency."""
    logger.info("[hitl] audit=%s", audit)
    return HumanMessage(content="confirmed")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        reply = await agent.ask("Request confirmation.")
        logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
