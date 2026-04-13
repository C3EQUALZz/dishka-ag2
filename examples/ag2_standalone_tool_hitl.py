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
from uuid import uuid4

from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import HumanInputRequest, HumanMessage, ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)

logger = logging.getLogger(__name__)


AuditLog = NewType("AuditLog", str)


class SessionMarker:
    def __init__(self) -> None:
        self.id = str(uuid4())


class AuditProvider(Provider):
    @provide(scope=AG2Scope.REQUEST)
    def audit_log(
        self,
        event: HumanInputRequest,
        session: SessionMarker,
    ) -> Iterable[AuditLog]:
        request_id = str(uuid4())
        log_entry = AuditLog(f"Human was asked: {event.content}")
        logger.info(
            "[hitl-request] created: request=%s session=%s audit=%s",
            request_id,
            session.id,
            log_entry,
        )
        yield log_entry
        logger.info(
            "[hitl-request] released: request=%s session=%s audit=%s",
            request_id,
            session.id,
            log_entry,
        )


class ConfirmationService:
    def __init__(
        self,
        *,
        tool_name: str,
        request_id: str,
        session_id: str,
    ) -> None:
        self.tool_name = tool_name
        self.request_id = request_id
        self.session_id = session_id
        self.confirmed = False


class ToolProvider(Provider):
    @provide(scope=AG2Scope.SESSION)
    def session_marker(self) -> Iterable[SessionMarker]:
        session = SessionMarker()
        logger.info("[session] created: session=%s", session.id)
        yield session
        logger.info("[session] released: session=%s", session.id)

    @provide(scope=AG2Scope.REQUEST)
    def confirmation_service(
        self,
        event: ToolCallEvent,
        session: SessionMarker,
    ) -> Iterable[ConfirmationService]:
        service = ConfirmationService(
            tool_name=event.name,
            request_id=str(uuid4()),
            session_id=session.id,
        )
        logger.info(
            "[tool-request] created: request=%s session=%s tool=%s",
            service.request_id,
            service.session_id,
            service.tool_name,
        )
        yield service
        logger.info(
            "[tool-request] released: request=%s session=%s confirmed=%s",
            service.request_id,
            service.session_id,
            service.confirmed,
        )


@tool  # type: ignore[untyped-decorator]
@inject
async def ask_human(
    context: Context,
    service: FromDishka[ConfirmationService],
) -> str:
    """Pauses agent execution to await human confirmation."""
    logger.info(
        "[tool] before human input: request=%s session=%s",
        service.request_id,
        service.session_id,
    )
    answer = await context.input("Please provide confirmation:")
    service.confirmed = True
    logger.info(
        "[tool] human said: %s, request=%s session=%s tool=%s confirmed=%s",
        answer,
        service.request_id,
        service.session_id,
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
    scopes=AG2Scope,
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


@agent.hitl_hook  # type: ignore[untyped-decorator]
@inject
async def on_human_input(  # noqa: RUF029
    event: HumanInputRequest,
    audit: FromDishka[AuditLog],
) -> HumanMessage:
    """HITL hook with injected audit dependency."""
    logger.info("[hitl] event=%s audit=%s", event.content, audit)
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
