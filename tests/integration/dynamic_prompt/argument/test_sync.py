"""Agent(..., prompt=...) with sync Dishka middleware."""

import pytest
from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import CONTAINER_NAME, FromDishka, inject
from tests.integration.conftest import sync_env
from tests.integration.dynamic_prompt.common import (
    PromptProvider,
    PromptService,
    TenantId,
)


@pytest.mark.asyncio()
async def test_init_prompt_uses_app_scope_via_dependencies_sync() -> None:
    async with sync_env(PromptProvider()) as (container, middleware):
        prompts: list[str] = []

        @inject
        def dynamic_prompt(
            ctx: Context,
            service: FromDishka[PromptService],
        ) -> str:
            built = service.build(ctx)
            prompts.append(built)
            return built

        agent = Agent(
            "assistant",
            prompt=dynamic_prompt,
            config=TestConfig(
                ToolCallEvent(name="noop", arguments="{}"),
                "Done.",
            ),
            dependencies={CONTAINER_NAME: container},
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        def noop() -> str:
            return "ok"

        await agent.ask("Hi!", variables={"tenant": "demo"})

    assert prompts
    assert "tenant" in prompts[0]


@pytest.mark.asyncio()
async def test_init_prompt_uses_request_scope_via_dependencies_sync() -> None:
    async with sync_env(PromptProvider()) as (container, middleware):
        prompts: list[str] = []

        @inject
        def dynamic_prompt(
            ctx: Context,
            tenant: FromDishka[TenantId],
        ) -> str:
            built = f"tenant={tenant} vars={ctx.variables}"
            prompts.append(built)
            return built

        agent = Agent(
            "assistant",
            prompt=dynamic_prompt,
            config=TestConfig(
                ToolCallEvent(name="noop", arguments="{}"),
                "Done.",
            ),
            dependencies={CONTAINER_NAME: container},
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        def noop() -> str:
            return "ok"

        await agent.ask("Hi!", variables={"tenant": "demo"})

    assert prompts
    assert "tenant=acme" in prompts[0]
