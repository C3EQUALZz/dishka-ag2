"""Code-defined ``MemorySkill`` + Dishka with an async container.

A ``MemorySkill`` script is a plain callable wrapped with ``tool()``, so an
``@inject`` script is the same ``tool(inject(...))`` composition as any other
injected tool. It runs through ``run_skill_script`` under the ``REQUEST`` scope
the middleware opens on ``on_tool_execution``. These tests prove the script
resolves fresh ``REQUEST``-scoped deps per call while ``SESSION`` stays shared,
and that an ``@inject`` Resource resolves an ``APP`` dep on ``read_skill_resource``.
"""

import pytest
from autogen.beta import Agent
from autogen.beta.testing import TestConfig

from tests.integration.conftest import async_env
from tests.integration.memory_skill.common import (
    APP_LABEL_VALUE,
    SKILL_INSTRUCTIONS_MARKER,
    MemorySkillProvider,
    ScriptRecords,
    build_async_skill,
    load_skill_call,
    make_result_collector,
    make_skill_plugin,
    make_skills_toolkit,
    read_resource_call,
    requires_memory_skill,
    run_script_call,
)

pytestmark = requires_memory_skill


@pytest.mark.asyncio()
async def test_memory_skill_script_request_scope_injects_async() -> None:
    records = ScriptRecords()
    skill = build_async_skill(records)
    outputs: list[str] = []

    async with async_env(MemorySkillProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                load_skill_call(),
                run_script_call(value=10, factor=2),
                run_script_call(value=5, factor=3),
                read_resource_call("app_label"),
                "All done.",
            ),
            tools=[make_skills_toolkit(skill)],
            observers=[make_result_collector(outputs)],
            middleware=[middleware],
        )

        await agent.ask("Convert 10 by 2, then 5 by 3, then read the app label.")

    # load_skill returned the in-memory instructions; the scripts actually ran.
    assert any(SKILL_INSTRUCTIONS_MARKER in out for out in outputs)
    assert "20.0" in outputs
    assert "15.0" in outputs

    # The script runs inside the REQUEST scope opened for the run_skill_script
    # tool call, fresh per call, while SESSION stays shared across the turn.
    assert records.tool_names == ["run_skill_script", "run_skill_script"]
    assert len(records.sessions) == 2
    assert records.sessions[0] == records.sessions[1]
    assert len(records.request_ids) == 2
    assert records.request_ids[0] != records.request_ids[1]

    # The @inject Resource resolved the APP-scoped dependency on read.
    assert records.resource_labels == [APP_LABEL_VALUE]
    assert f"app={APP_LABEL_VALUE}" in outputs


@pytest.mark.asyncio()
async def test_memory_skill_plugin_path_request_scope_injects_async() -> None:
    """A ``MemorySkill`` attached via ``plugins=[SkillPlugin(...)]`` behaves the same.

    ``SkillPlugin`` injects the catalog into the prompt and exposes
    ``run_skill_script``; the in-process script keeps resolving fresh
    ``REQUEST``-scoped dependencies on each call.
    """
    records = ScriptRecords()
    skill = build_async_skill(records)
    outputs: list[str] = []

    async with async_env(MemorySkillProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                run_script_call(value=10, factor=2),
                run_script_call(value=5, factor=3),
                "All done.",
            ),
            plugins=[make_skill_plugin(skill)],
            observers=[make_result_collector(outputs)],
            middleware=[middleware],
        )

        await agent.ask("Convert 10 by 2, then 5 by 3.")

    assert "20.0" in outputs
    assert "15.0" in outputs
    assert len(records.sessions) == 2
    assert records.sessions[0] == records.sessions[1]
    assert len(records.request_ids) == 2
    assert records.request_ids[0] != records.request_ids[1]
