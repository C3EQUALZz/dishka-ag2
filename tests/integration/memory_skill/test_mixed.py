"""Sync and async scripts and resources in one MemorySkill."""

import json

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig
from ag2.tools.skills import MemorySkill
from dishka import AsyncContainer

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.integration.conftest import async_env
from tests.integration.memory_skill.common import (
    APP_LABEL_VALUE,
    SKILL_DESCRIPTION,
    SKILL_INSTRUCTIONS,
    SKILL_INSTRUCTIONS_MARKER,
    SKILL_NAME,
    AppLabel,
    MemorySkillProvider,
    ScriptRecords,
    load_skill_call,
    make_result_collector,
    make_skill_plugin,
    make_skills_toolkit,
    read_resource_call,
)
from tests.integration.scope_state import SessionState, ToolRequestState


@pytest.mark.asyncio()
@pytest.mark.parametrize("registration", ("toolkit", "plugin"))
async def test_memory_skill_with_mixed_callbacks(registration: str) -> None:
    records = ScriptRecords()
    requests: list[AsyncContainer] = []
    outputs: list[str] = []
    skill = MemorySkill(
        name=SKILL_NAME,
        description=SKILL_DESCRIPTION,
        instructions=SKILL_INSTRUCTIONS,
    )

    def record(
        session: SessionState,
        request: ToolRequestState,
        container: AsyncContainer,
    ) -> None:
        records.sessions.append(session.session_id)
        records.request_ids.append(request.request_id)
        records.tool_names.append(request.tool_name)
        requests.append(container)

    @skill.script(description="Convert synchronously.")
    @inject
    def sync_convert(
        value: float,
        factor: float,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
        container: FromDishka[AsyncContainer],
    ) -> str:
        record(session, request, container)
        return f"sync={value * factor}"

    @skill.script(description="Convert asynchronously.")
    @inject
    async def async_convert(
        value: float,
        factor: float,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
        container: FromDishka[AsyncContainer],
    ) -> str:
        record(session, request, container)
        return f"async={value * factor}"

    @skill.resource(description="Read the label synchronously.")
    @inject
    def sync_label(
        label: FromDishka[AppLabel],
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
        container: FromDishka[AsyncContainer],
    ) -> str:
        record(session, request, container)
        records.resource_labels.append(label)
        return f"sync app={label}"

    @skill.resource(description="Read the label asynchronously.")
    @inject
    async def async_label(
        label: FromDishka[AppLabel],
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
        container: FromDishka[AsyncContainer],
    ) -> str:
        record(session, request, container)
        records.resource_labels.append(label)
        return f"async app={label}"

    script_calls = [
        ToolCallEvent(
            name="run_skill_script",
            arguments=json.dumps(
                {
                    "name": SKILL_NAME,
                    "script": script,
                    "args": {"value": value, "factor": factor},
                },
            ),
        )
        for script, value, factor in (("sync_convert", 10, 2), ("async_convert", 5, 3))
    ]
    async with async_env(MemorySkillProvider()) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                load_skill_call(),
                *script_calls,
                read_resource_call("sync_label"),
                read_resource_call("async_label"),
                "Done.",
            ),
            tools=[make_skills_toolkit(skill)] if registration == "toolkit" else [],
            plugins=[make_skill_plugin(skill)] if registration == "plugin" else [],
            observers=[make_result_collector(outputs)],
            middleware=[middleware],
        )
        await agent.ask("Run both scripts and read both resources.")

    assert any(SKILL_INSTRUCTIONS_MARKER in output for output in outputs)
    assert "sync=20.0" in outputs
    assert "async=15.0" in outputs
    assert f"sync app={APP_LABEL_VALUE}" in outputs
    assert f"async app={APP_LABEL_VALUE}" in outputs
    assert len(records.sessions) == 4
    assert len(set(records.sessions)) == 1
    assert len(set(records.request_ids)) == 4
    assert records.tool_names == [
        "run_skill_script",
        "run_skill_script",
        "read_skill_resource",
        "read_skill_resource",
    ]
    assert records.resource_labels == [APP_LABEL_VALUE, APP_LABEL_VALUE]
    assert all(container.scope is AG2Scope.REQUEST for container in requests)
    assert all(
        container.parent_container is requests[0].parent_container
        for container in requests
    )
