"""Shared helpers for the agent-skills integration tests."""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

from ag2.events import ToolCallEvent, ToolResultEvent
from ag2.observers import observer
from ag2.tools.skills import LocalRuntime, SkillPlugin, SkillsToolkit
from dishka import Provider, provide

from dishka_ag2 import AG2Scope
from tests.integration.scope_state import SessionState, ToolRequestState

if TYPE_CHECKING:
    from ag2.observers import Observer
    from ag2.plugin import Plugin
    from ag2.tools import Toolkit

SKILL_NAME = "greeting"
SKILL_DESCRIPTION = "Produce a friendly greeting for a given person."
SKILL_BODY = """\
---
name: greeting
description: Produce a friendly greeting for a given person.
---

# Greeting skill

Use this skill to greet a person warmly.

1. Take the person's name.
2. Return "Hello, <name>!".
"""
# Marker text from the SKILL.md body that proves the file was actually read.
SKILL_BODY_MARKER = "Use this skill to greet a person warmly."


def write_skill(skills_dir: Path) -> Path:
    """Create the ``greeting`` skill under ``skills_dir`` and return its root."""
    skill_dir = skills_dir / SKILL_NAME
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(SKILL_BODY, encoding="utf-8")
    return skills_dir


def make_skills_toolkit(skills_dir: Path) -> "Toolkit":
    """Build a SkillsToolkit rooted at ``skills_dir``."""
    return SkillsToolkit(LocalRuntime(str(skills_dir)))


def make_skill_plugin(skills_dir: Path) -> "Plugin":
    """Build a SkillPlugin rooted at ``skills_dir``."""
    return SkillPlugin(str(skills_dir))


def tool_result_text(event: ToolResultEvent) -> str:
    """Extract the textual payload from a ToolResultEvent."""
    result = event.result
    if not result.parts:
        return str(result)
    part = result.parts[0]
    return part.content if hasattr(part, "content") else str(part)  # type: ignore[no-any-return,unused-ignore]


def make_result_collector(sink: list[str]) -> "Observer":
    """An observer that appends every ToolResultEvent's text to ``sink``."""
    return observer(ToolResultEvent, lambda event: sink.append(tool_result_text(event)))


class SkillsProvider(Provider):
    """REQUEST-scoped deps to assert injection works alongside skills."""

    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()

    @provide(scope=AG2Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=AG2Scope.SESSION)
    def session_state(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)
