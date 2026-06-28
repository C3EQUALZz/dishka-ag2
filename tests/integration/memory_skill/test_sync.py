"""Code-defined ``MemorySkill`` + Dishka with a sync container.

Mirrors ``test_async`` but drives a synchronous Dishka container: an in-process
``@inject`` script (run via ``run_skill_script``) resolves fresh ``REQUEST``-scoped
dependencies on each call while ``SESSION`` stays shared across the turn.
"""

import pytest
from autogen.beta import Agent
from autogen.beta.testing import TestConfig

from tests.integration.conftest import sync_env
from tests.integration.memory_skill.common import (
    SKILL_INSTRUCTIONS_MARKER,
    MemorySkillProvider,
    ScriptRecords,
    build_sync_skill,
    load_skill_call,
    make_result_collector,
    make_skills_toolkit,
    requires_memory_skill,
    run_script_call,
)

pytestmark = requires_memory_skill


@pytest.mark.asyncio()
async def test_memory_skill_script_request_scope_injects_sync() -> None:
    records = ScriptRecords()
    skill = build_sync_skill(records)
    outputs: list[str] = []

    async with sync_env(MemorySkillProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                load_skill_call(),
                run_script_call(value=10, factor=2),
                run_script_call(value=5, factor=3),
                "All done.",
            ),
            tools=[make_skills_toolkit(skill)],
            observers=[make_result_collector(outputs)],
            middleware=[middleware],
        )

        await agent.ask("Convert 10 by 2, then 5 by 3.")

    # load_skill returned the in-memory instructions; the scripts actually ran.
    assert any(SKILL_INSTRUCTIONS_MARKER in out for out in outputs)
    assert "20.0" in outputs
    assert "15.0" in outputs

    # REQUEST-scoped deps injected into the in-process script, fresh per call,
    # while SESSION stayed shared across the turn.
    assert records.tool_names == ["run_skill_script", "run_skill_script"]
    assert len(records.sessions) == 2
    assert records.sessions[0] == records.sessions[1]
    assert len(records.request_ids) == 2
    assert records.request_ids[0] != records.request_ids[1]
