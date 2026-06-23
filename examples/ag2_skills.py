"""Example: AG2 agent skills with Dishka-injected tools.

Agent skills (``autogen.beta.tools.skills``) were added in ag2 0.13.4. A skill
is a directory holding a ``SKILL.md`` file; ``SkillsToolkit`` exposes the
progressive-disclosure tools (``list_skills`` / ``load_skill`` /
``read_skill_resource`` / ``run_skill_script``) so the model can discover and
load skills on demand.

Those skill tools are ordinary local tools, so they run under the same
``REQUEST`` scope the Dishka middleware opens on every ``on_tool_execution``.
This example shows a skill being loaded while the agent's own ``@inject`` tool
resolves fresh ``REQUEST``-scoped dependencies on each call.
"""

import asyncio
import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent, ToolResultEvent
from autogen.beta.middleware import Middleware
from autogen.beta.observers import observer
from autogen.beta.testing import TestConfig
from autogen.beta.tools import tool
from autogen.beta.tools.skills import LocalRuntime, SkillsToolkit
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)

logger = logging.getLogger(__name__)

SKILL_MD = """\
---
name: greeting
description: Produce a friendly greeting for a given person.
---

# Greeting skill

Use this skill to greet a person warmly.

1. Take the person's name.
2. Return "Hello, <name>!".
"""


def install_demo_skill(skills_dir: Path) -> None:
    """Write a minimal ``greeting`` skill into ``skills_dir``."""
    skill_dir = skills_dir / "greeting"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")


@dataclass(frozen=True)
class SessionState:
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolRequestState:
    tool_name: str
    request_id: UUID = field(default_factory=uuid4)


class MyProvider(Provider):
    @provide(scope=AG2Scope.SESSION)
    def session_state(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)


@tool
@inject
async def remember(
    name: str,
    session: FromDishka[SessionState],
    request: FromDishka[ToolRequestState],
) -> str:
    logger.info(
        "[injected tool] remembering %s session=%s request=%s tool=%s",
        name,
        session.session_id,
        request.request_id,
        request.tool_name,
    )
    return f"remembered {name}"


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp) / "skills"
        install_demo_skill(skills_dir)

        provider = MyProvider()
        container = make_async_container(provider, AG2Provider(), scopes=AG2Scope)

        # Log every skill tool result so you can see the SKILL.md body that the
        # model would receive after calling load_skill(...).
        log_skill_output = observer(
            ToolResultEvent,
            lambda event: logger.info("[skill output]\n%s", _result_text(event)),
        )

        agent = Agent(
            "assistant",
            prompt="Load the greeting skill, then remember the people mentioned.",
            config=TestConfig(
                ToolCallEvent(name="load_skill", arguments='{"name": "greeting"}'),
                ToolCallEvent(name="remember", arguments='{"name": "Alice"}'),
                ToolCallEvent(name="remember", arguments='{"name": "Bob"}'),
                "All done.",
            ),
            tools=[
                SkillsToolkit(LocalRuntime(str(skills_dir))),
                remember,
            ],
            observers=[log_skill_output],
            middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
        )

        try:
            reply = await agent.ask("Load the greeting skill, then remember Alice and Bob.")
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
