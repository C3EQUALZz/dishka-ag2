"""A decorated sync or async HITL hook alongside mixed tools."""

import pytest
from ag2 import Agent
from ag2.annotations import Context
from ag2.events import HumanInputRequest, HumanMessage, ToolCallEvent
from ag2.testing import TestConfig
from dishka import AsyncContainer

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.hitl.common import AuditLog, ConfirmationService, HitlProvider


@pytest.mark.asyncio()
@pytest.mark.parametrize("hook_kind", ("sync", "async"))
async def test_hitl_decorator_with_mixed_tools(hook_kind: str) -> None:
    provider = HitlProvider()
    calls: list[tuple[str, AsyncContainer]] = []

    @inject
    def sync_hook(
        event: HumanInputRequest,
        audit: FromDishka[AuditLog],
        container: FromDishka[AsyncContainer],
    ) -> HumanMessage:
        assert audit == AuditLog(f"asked: {event.content}")
        calls.append(("sync hook", container))
        return HumanMessage(content="approved")

    @inject
    async def async_hook(
        event: HumanInputRequest,
        audit: FromDishka[AuditLog],
        container: FromDishka[AsyncContainer],
    ) -> HumanMessage:
        assert audit == AuditLog(f"asked: {event.content}")
        calls.append(("async hook", container))
        return HumanMessage(content="approved")

    async with async_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="sync_tool", arguments="{}"),
                ToolCallEvent(name="ask_human", arguments="{}"),
                "Done.",
            ),
            middleware=[middleware],
        )
        agent.hitl_hook(sync_hook if hook_kind == "sync" else async_hook)

        @agent.tool
        @inject
        def sync_tool(
            service: FromDishka[ConfirmationService],
            container: FromDishka[AsyncContainer],
        ) -> str:
            assert service.tool_name == "sync_tool"
            calls.append(("sync tool", container))
            return "ok"

        @agent.tool
        @inject
        async def ask_human(
            ctx: Context,
            service: FromDishka[ConfirmationService],
            container: FromDishka[AsyncContainer],
        ) -> str:
            assert service.tool_name == "ask_human"
            calls.append(("async tool", container))
            answer = await ctx.input("Approve?")
            assert answer == "approved"
            return answer

        await agent.ask("Check and ask for confirmation.")

    assert [name for name, _ in calls] == ["sync tool", "async tool", f"{hook_kind} hook"]
    requests = [container for _, container in calls]
    assert len({id(container) for container in requests}) == 3
    assert all(container.scope is AG2Scope.REQUEST for container in requests)
    assert all(
        container.parent_container is requests[0].parent_container
        for container in requests
    )
    provider.audit_released.assert_called_once()
