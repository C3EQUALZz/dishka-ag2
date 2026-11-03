"""Sync and async dynamic prompts registered as decorators."""

import pytest
from ag2 import Agent
from ag2.annotations import Context
from ag2.testing import TestConfig
from dishka import AsyncContainer

from dishka_ag2 import CONTAINER_NAME, AG2Scope, FromDishka, inject
from dishka_ag2._container import walk_to_root
from tests.common import REQUEST_DEP_VALUE, AppProvider, RequestDep
from tests.integration.conftest import async_env
from tests.integration.dynamic_prompt.common import (
    PromptProvider,
    PromptService,
    TenantId,
)


@pytest.mark.asyncio()
async def test_prompt_decorators_with_mixed_functions(app_provider: AppProvider) -> None:
    calls: list[tuple[str, str, AsyncContainer]] = []

    async with async_env(app_provider, PromptProvider()) as (root, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig("Done."),
            dependencies={CONTAINER_NAME: root},
            middleware=[middleware],
        )

        @agent.prompt
        @inject
        def sync_prompt(
            ctx: Context,
            service: FromDishka[PromptService],
            tenant: FromDishka[TenantId],
            request: FromDishka[RequestDep],
            container: FromDishka[AsyncContainer],
        ) -> str:
            assert request == REQUEST_DEP_VALUE
            prompt = f"sync tenant={tenant} {service.build(ctx)}"
            calls.append(("sync", prompt, container))
            return prompt

        @agent.prompt
        @inject
        async def async_prompt(
            ctx: Context,
            service: FromDishka[PromptService],
            tenant: FromDishka[TenantId],
            request: FromDishka[RequestDep],
            container: FromDishka[AsyncContainer],
        ) -> str:
            assert request == REQUEST_DEP_VALUE
            prompt = f"async tenant={tenant} {service.build(ctx)}"
            calls.append(("async", prompt, container))
            return prompt

        await agent.ask("Build both prompts.", variables={"tenant": "demo"})
        assert agent.dependencies[CONTAINER_NAME] is root

    assert [name for name, _, _ in calls] == ["sync", "async"]
    assert all("tenant=acme" in prompt and "demo" in prompt for _, prompt, _ in calls)
    sync_request, async_request = (container for _, _, container in calls)
    assert sync_request is not async_request
    assert sync_request.scope is async_request.scope is AG2Scope.REQUEST
    assert walk_to_root(sync_request) is walk_to_root(async_request) is root
    assert app_provider.request_released.call_count == 2
