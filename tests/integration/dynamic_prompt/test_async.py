"""@agent.prompt with APP- and REQUEST-scope DI.

Mirrors examples/ag2_dynamic_prompt.py. Dynamic prompts run before middleware
is constructed, so the user must pass the container via `dependencies=`.
"""

from typing import NewType

import pytest
from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from dishka import Provider, Scope, provide

from dishka_ag2 import CONTAINER_NAME, FromDishka, inject
from tests.integration.conftest import async_env

TenantId = NewType("TenantId", str)


class PromptService:
    async def build(self, context: Context) -> str:
        return f"vars={context.variables}"


class PromptProvider(Provider):
    @provide(scope=Scope.APP)
    def prompt_service(self) -> PromptService:
        return PromptService()

    @provide(scope=Scope.REQUEST)
    def tenant(self) -> TenantId:
        return TenantId("acme")


@pytest.mark.asyncio()
async def test_agent_prompt_uses_app_scope_via_dependencies() -> None:
    async with async_env(PromptProvider()) as (container, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="noop", arguments="{}"),
                "Done.",
            ),
            dependencies={CONTAINER_NAME: container},
            middleware=[middleware],
        )

        prompts: list[str] = []

        @agent.prompt  # type: ignore[untyped-decorator]
        @inject
        async def dynamic_prompt(
            ctx: Context,
            service: FromDishka[PromptService],
        ) -> str:
            built = await service.build(ctx)
            prompts.append(built)
            return built

        @agent.tool  # type: ignore[untyped-decorator]
        async def noop() -> str:
            return "ok"

        await agent.ask("Hi!", variables={"tenant": "demo"})

    assert prompts
    assert "tenant" in prompts[0]


@pytest.mark.asyncio()
async def test_agent_prompt_uses_request_scope_via_dependencies() -> None:
    async with async_env(PromptProvider()) as (container, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="noop", arguments="{}"),
                "Done.",
            ),
            dependencies={CONTAINER_NAME: container},
            middleware=[middleware],
        )

        prompts: list[str] = []

        @agent.prompt  # type: ignore[untyped-decorator]
        @inject
        async def dynamic_prompt(
            ctx: Context,
            tenant: FromDishka[TenantId],
        ) -> str:
            built = f"tenant={tenant} vars={ctx.variables}"
            prompts.append(built)
            return built

        @agent.tool  # type: ignore[untyped-decorator]
        async def noop() -> str:
            return "ok"

        await agent.ask("Hi!", variables={"tenant": "demo"})

    assert prompts
    assert "tenant=acme" in prompts[0]
