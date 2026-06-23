"""Shared helpers for the agent-skills integration tests.

Agent skills (``autogen.beta.tools.skills``) were added in ag2 0.13.4. The
``requires_skills`` marker skips the whole package on older releases (run in
the nox matrix), and the ``SkillsToolkit`` import is guarded so importing this
module never fails there.
"""

from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from autogen.beta.events import ToolCallEvent, ToolResultEvent
from dishka import Provider, provide
from packaging.version import Version

from dishka_ag2 import AG2Scope
from tests.integration.scope_state import SessionState, ToolRequestState

if TYPE_CHECKING:
    from autogen.beta.observers import Observer
    from autogen.beta.tools import Toolkit

AG2_VERSION = Version(version("ag2"))
SKILLS_MIN_VERSION = Version("0.13.4")
SKILLS_AVAILABLE = AG2_VERSION >= SKILLS_MIN_VERSION

requires_skills = pytest.mark.skipif(
    not SKILLS_AVAILABLE,
    reason=f"agent skills require ag2 >= {SKILLS_MIN_VERSION} (running {AG2_VERSION})",
)

if SKILLS_AVAILABLE:
    # ``autogen.beta.observers`` is also new in 0.13.4, so it must stay behind
    # the version guard or older nox-matrix runs fail to import this module.
    from autogen.beta.observers import observer
    from autogen.beta.tools.skills import LocalRuntime, SkillsToolkit

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
    """Build a SkillsToolkit rooted at ``skills_dir`` (ag2 >= 0.13.4 only)."""
    return SkillsToolkit(LocalRuntime(str(skills_dir)))


def tool_result_text(event: ToolResultEvent) -> str:
    """Extract textual payload from a ToolResultEvent across ag2 versions."""
    result = event.result
    if hasattr(result, "parts"):
        part = result.parts[0]
        return part.content if hasattr(part, "content") else str(part)  # type: ignore[no-any-return,unused-ignore]
    return result.content  # type: ignore[no-any-return,attr-defined,unused-ignore]


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
