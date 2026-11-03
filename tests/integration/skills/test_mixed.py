"""Filesystem skills alongside sync and async injected tools."""

from pathlib import Path

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.scope_state import SessionState, ToolRequestState
from tests.integration.skills.common import (
    SKILL_BODY_MARKER,
    SKILL_NAME,
    SkillsProvider,
    make_result_collector,
    make_skill_plugin,
    make_skills_toolkit,
)


@pytest.mark.asyncio()
@pytest.mark.parametrize("registration", ("toolkit", "plugin"))
async def test_skills_with_mixed_tools(skills_dir: Path, registration: str) -> None:
    calls: list[tuple[str, SessionState, ToolRequestState]] = []
    outputs: list[str] = []

    @inject
    def sync_remember(
        name: str,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
    ) -> str:
        calls.append(("sync", session, request))
        return f"sync remembered {name}"

    @inject
    async def async_remember(
        name: str,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
    ) -> str:
        calls.append(("async", session, request))
        return f"async remembered {name}"

    async with async_env(SkillsProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="load_skill", arguments=f'{{"name": "{SKILL_NAME}"}}'),
                ToolCallEvent(name="sync_remember", arguments='{"name": "Alice"}'),
                ToolCallEvent(name="async_remember", arguments='{"name": "Bob"}'),
                "Done.",
            ),
            tools=(
                [make_skills_toolkit(skills_dir), sync_remember, async_remember]
                if registration == "toolkit"
                else [sync_remember, async_remember]
            ),
            plugins=[make_skill_plugin(skills_dir)] if registration == "plugin" else [],
            observers=[make_result_collector(outputs)],
            middleware=[middleware],
        )
        await agent.ask("Load the greeting skill and remember Alice and Bob.")

    assert any(SKILL_BODY_MARKER in output for output in outputs)
    assert "sync remembered Alice" in outputs
    assert "async remembered Bob" in outputs
    assert [name for name, _, _ in calls] == ["sync", "async"]
    _, sync_session, sync_request = calls[0]
    _, async_session, async_request = calls[1]
    assert sync_session is async_session
    assert sync_request.request_id != async_request.request_id
    assert sync_request.tool_name == "sync_remember"
    assert async_request.tool_name == "async_remember"
