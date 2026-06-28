"""Shared helpers for the code-defined ``MemorySkill`` integration tests.

``MemorySkill`` / ``MemoryRuntime`` (``autogen.beta.tools.skills``) were added
in ag2 0.14.0: a skill is defined inline in code, carrying its instructions,
Resources and Scripts as in-memory values instead of files on disk. Scripts and
Resources are wrapped with ``tool()`` and invoked through the same FastDepends
path as any other tool, threading the live ``Context`` -- so an ``@inject``
script/resource resolves Dishka dependencies exactly like a regular tool does.

The ``requires_memory_skill`` marker skips the whole package on older releases
(run in the nox matrix), and every ``MemorySkill`` import is guarded so importing
this module never fails there.
"""

from dataclasses import dataclass, field
from importlib.metadata import version
from typing import TYPE_CHECKING, NewType
from uuid import UUID

import pytest
from autogen.beta.events import ToolCallEvent, ToolResultEvent
from dishka import Provider, provide
from packaging.version import Version

from dishka_ag2 import AG2Scope, FromDishka, inject
from tests.integration.scope_state import SessionState, ToolRequestState

if TYPE_CHECKING:
    from autogen.beta.observers import Observer
    from autogen.beta.plugin import Plugin
    from autogen.beta.tools import Toolkit
    from autogen.beta.tools.skills import MemorySkill

AG2_VERSION = Version(version("ag2"))
MEMORY_SKILL_MIN_VERSION = Version("0.14.0")
MEMORY_SKILL_AVAILABLE = AG2_VERSION >= MEMORY_SKILL_MIN_VERSION

SKIP_REASON = (
    f"MemorySkill requires ag2 >= {MEMORY_SKILL_MIN_VERSION} (running {AG2_VERSION})"
)
requires_memory_skill = pytest.mark.skipif(
    not MEMORY_SKILL_AVAILABLE,
    reason=SKIP_REASON,
)

if MEMORY_SKILL_AVAILABLE:
    # The skills package is also restructured in 0.14.0, so every import here
    # must stay behind the version guard or older nox-matrix runs fail to import
    # this module.
    from autogen.beta.observers import observer
    from autogen.beta.tools.skills import MemorySkill, SkillPlugin, SkillsToolkit

AppLabel = NewType("AppLabel", str)
APP_LABEL_VALUE = AppLabel("memory-skill-app")

SKILL_NAME = "unit-converter"
SKILL_DESCRIPTION = "Convert a value between units by multiplying it by a factor."
# Marker text from the skill instructions that proves load_skill actually ran.
SKILL_INSTRUCTIONS_MARKER = "Multiply the value by the factor to convert it."
SKILL_INSTRUCTIONS = f"""\
# Unit converter

{SKILL_INSTRUCTIONS_MARKER}

Call the ``convert`` script with ``value`` and ``factor``.
"""


@dataclass
class ScriptRecords:
    """Captures what the injected script/resource saw on each invocation."""

    sessions: list[UUID] = field(default_factory=list)
    request_ids: list[UUID] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    resource_labels: list[str] = field(default_factory=list)


def build_async_skill(records: ScriptRecords) -> "MemorySkill":
    """A code-defined skill whose async script and resource use ``@inject``."""
    skill = MemorySkill(
        name=SKILL_NAME,
        description=SKILL_DESCRIPTION,
        instructions=SKILL_INSTRUCTIONS,
    )

    @skill.script(description="Multiply value by factor.")
    @inject
    async def convert(
        value: float,
        factor: float,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
    ) -> str:
        records.sessions.append(session.session_id)
        records.request_ids.append(request.request_id)
        records.tool_names.append(request.tool_name)
        return str(value * factor)

    @skill.resource(description="The running app's label.")
    @inject
    async def app_label(label: FromDishka[AppLabel]) -> str:
        records.resource_labels.append(label)
        return f"app={label}"

    return skill


def build_sync_skill(records: ScriptRecords) -> "MemorySkill":
    """A code-defined skill whose sync script uses ``@inject``."""
    skill = MemorySkill(
        name=SKILL_NAME,
        description=SKILL_DESCRIPTION,
        instructions=SKILL_INSTRUCTIONS,
    )

    @skill.script(description="Multiply value by factor.")
    @inject
    def convert(
        value: float,
        factor: float,
        session: FromDishka[SessionState],
        request: FromDishka[ToolRequestState],
    ) -> str:
        records.sessions.append(session.session_id)
        records.request_ids.append(request.request_id)
        records.tool_names.append(request.tool_name)
        return str(value * factor)

    return skill


def make_skills_toolkit(skill: "MemorySkill") -> "Toolkit":
    """Wrap a code-defined skill in a SkillsToolkit (ag2 >= 0.14.0 only)."""
    return SkillsToolkit(skill)


def make_skill_plugin(skill: "MemorySkill") -> "Plugin":
    """Wrap a code-defined skill in a SkillPlugin (ag2 >= 0.14.0 only)."""
    return SkillPlugin(skill)


def run_script_call(value: float, factor: float) -> ToolCallEvent:
    """A ``run_skill_script`` call invoking the in-process ``convert`` script."""
    arguments = (
        f'{{"name": "{SKILL_NAME}", "script": "convert", '
        f'"args": {{"value": {value}, "factor": {factor}}}}}'
    )
    return ToolCallEvent(name="run_skill_script", arguments=arguments)


def load_skill_call() -> ToolCallEvent:
    return ToolCallEvent(name="load_skill", arguments=f'{{"name": "{SKILL_NAME}"}}')


def read_resource_call(resource: str) -> ToolCallEvent:
    return ToolCallEvent(
        name="read_skill_resource",
        arguments=f'{{"name": "{SKILL_NAME}", "resource": "{resource}"}}',
    )


def tool_result_text(event: ToolResultEvent) -> str:
    """Extract textual payload from a ToolResultEvent across ag2 versions."""
    result = event.result
    parts = getattr(result, "parts", None)
    if parts:
        part = parts[0]
        return part.content if hasattr(part, "content") else str(part)  # type: ignore[no-any-return,unused-ignore]
    if hasattr(result, "content"):
        return result.content  # type: ignore[no-any-return,attr-defined,unused-ignore]
    return str(result)


def make_result_collector(sink: list[str]) -> "Observer":
    """An observer that appends every ToolResultEvent's text to ``sink``."""
    return observer(ToolResultEvent, lambda event: sink.append(tool_result_text(event)))


class MemorySkillProvider(Provider):
    """APP/SESSION/REQUEST deps to assert injection works inside a skill."""

    @provide(scope=AG2Scope.APP)
    def app_label(self) -> AppLabel:
        return APP_LABEL_VALUE

    @provide(scope=AG2Scope.SESSION)
    def session_state(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)
