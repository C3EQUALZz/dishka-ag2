"""Agent skills + Dishka with a sync container.

Mirrors ``test_async`` but drives a synchronous Dishka container: a skill tool
(``load_skill``) executes while a user's own ``@inject`` tool resolves fresh
REQUEST-scoped dependencies on each call.
"""

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool

from dishka_ag2 import FromDishka, inject
from tests.integration.conftest import sync_env
from tests.integration.scope_state import SessionState, ToolRequestState
from tests.integration.skills.common import (
    SKILL_BODY_MARKER,
    SKILL_NAME,
    SkillsProvider,
    make_result_collector,
    make_skills_toolkit,
    requires_skills,
)

if TYPE_CHECKING:
    from uuid import UUID

pytestmark = requires_skills


@pytest.mark.asyncio()
async def test_skill_executes_and_request_scope_injects_sync(skills_dir: Path) -> None:
    provider = SkillsProvider()
    sessions: list[UUID] = []
    tool_names: list[str] = []
    skill_outputs: list[str] = []

    @tool
    @inject
    def remember(
        name: str,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
    ) -> str:
        sessions.append(session.session_id)
        tool_names.append(request.tool_name)
        return f"remembered {name}"

    collect_results = make_result_collector(skill_outputs)

    async with sync_env(provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="load_skill", arguments=f'{{"name": "{SKILL_NAME}"}}'),
                ToolCallEvent(name="remember", arguments='{"name": "Alice"}'),
                ToolCallEvent(name="remember", arguments='{"name": "Bob"}'),
                "All done.",
            ),
            tools=[make_skills_toolkit(skills_dir), remember],
            observers=[collect_results],
            middleware=[middleware],
        )

        await agent.ask("Load the greeting skill, then remember Alice and Bob.")

    # The skill tool actually ran and returned the SKILL.md body.
    assert any(SKILL_BODY_MARKER in out for out in skill_outputs)

    # REQUEST-scoped deps injected into the user's own tool, fresh per call,
    # while SESSION stayed shared across the turn.
    assert tool_names == ["remember", "remember"]
    assert len(sessions) == 2
    assert sessions[0] == sessions[1]
