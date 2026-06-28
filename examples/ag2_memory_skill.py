"""Example: a code-defined ``MemorySkill`` with Dishka-injected scripts.

``MemorySkill`` (``autogen.beta.tools.skills``, ag2 >= 0.14.0) defines a skill
inline in code instead of on disk: its instructions, Resources and Scripts are
in-memory values registered with ``@skill.resource`` / ``@skill.script``.

Each Resource/Script callable is wrapped with ``tool()`` and invoked through the
same FastDepends path as any other tool, threading the live ``Context`` -- so an
``@inject`` script resolves Dishka dependencies exactly like a regular tool.
A ``MemorySkill`` (or the ``MemoryRuntime`` that owns it) is passed straight to
``SkillPlugin`` (the recommended option) or ``SkillsToolkit``, which exposes
``run_skill_script(...)`` to the model. That tool runs under the same ``REQUEST``
scope the middleware opens on every ``on_tool_execution``, so the in-process
script gets fresh ``REQUEST``-scoped dependencies on each call.

``SkillPlugin`` injects the skill catalog into the system prompt and registers
only the activation tools the skills actually need (``load_skill``,
``read_skill_resource``, ``run_skill_script``).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import NewType
from uuid import UUID, uuid4

from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent, ToolResultEvent
from autogen.beta.middleware import Middleware
from autogen.beta.observers import observer
from autogen.beta.testing import TestConfig
from autogen.beta.tools.skills import MemorySkill, SkillPlugin
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)

logger = logging.getLogger(__name__)

AppLabel = NewType("AppLabel", str)


@dataclass(frozen=True)
class SessionState:
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolRequestState:
    tool_name: str
    request_id: UUID = field(default_factory=uuid4)


class MyProvider(Provider):
    @provide(scope=AG2Scope.APP)
    def app_label(self) -> AppLabel:
        return AppLabel("memory-skill-app")

    @provide(scope=AG2Scope.SESSION)
    def session_state(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)


def build_unit_converter_skill() -> MemorySkill:
    """A code-defined skill whose script and resource use ``@inject``."""
    skill = MemorySkill(
        name="unit-converter",
        description="Convert a value between units by multiplying it by a factor.",
        instructions=(
            "# Unit converter\n\n"
            "Multiply the value by the factor to convert it.\n"
            "Call the `convert` script with `value` and `factor`."
        ),
    )

    @skill.script(description="Multiply value by factor.")
    @inject
    async def convert(
        value: float,
        factor: float,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
    ) -> str:
        logger.info(
            "[skill script] convert(%s, %s) session=%s request=%s tool=%s",
            value,
            factor,
            session.session_id,
            request.request_id,
            request.tool_name,
        )
        return str(value * factor)

    @skill.resource(description="The running app's label.")
    @inject
    async def app_label(label: FromDishka[AppLabel]) -> str:
        logger.info("[skill resource] app_label -> %s", label)
        return f"app={label}"

    return skill


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    provider = MyProvider()
    container = make_async_container(provider, AG2Provider(), scopes=AG2Scope)

    # Log every skill tool result so you can see what the model would receive.
    log_skill_output = observer(
        ToolResultEvent,
        lambda event: logger.info("[skill output]\n%s", _result_text(event)),
    )

    agent = Agent(
        "assistant",
        prompt="Convert values with the unit-converter skill.",
        config=TestConfig(
            ToolCallEvent(name="load_skill", arguments='{"name": "unit-converter"}'),
            ToolCallEvent(
                name="run_skill_script",
                arguments='{"name": "unit-converter", "script": "convert", "args": {"value": 10, "factor": 2}}',
            ),
            ToolCallEvent(
                name="run_skill_script",
                arguments='{"name": "unit-converter", "script": "convert", "args": {"value": 5, "factor": 3}}',
            ),
            ToolCallEvent(
                name="read_skill_resource",
                arguments='{"name": "unit-converter", "resource": "app_label"}',
            ),
            "All done.",
        ),
        # A loose MemorySkill is wrapped in a MemoryRuntime automatically.
        # SkillPlugin (recommended) injects the catalog into the prompt and
        # exposes load_skill / read_skill_resource / run_skill_script.
        plugins=[SkillPlugin(build_unit_converter_skill())],
        observers=[log_skill_output],
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    try:
        reply = await agent.ask("Convert 10 by 2, then 5 by 3, then read the app label.")
        logger.info("[agent] %s", reply.body)
    finally:
        await container.close()


def _result_text(event: ToolResultEvent) -> str:
    result = event.result
    if hasattr(result, "parts"):
        part = result.parts[0]
        return part.content if hasattr(part, "content") else str(part)
    return result.content


if __name__ == "__main__":
    asyncio.run(main())
