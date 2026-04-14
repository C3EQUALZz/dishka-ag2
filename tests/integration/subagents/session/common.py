from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from autogen.beta.annotations import Context
from autogen.beta.events import ToolCallEvent
from dishka import Provider, provide

from dishka_ag2 import AG2Scope
from tests.integration.subagents.common import AppTrace


@dataclass(frozen=True)
class SessionTrace:
    agent_name: str
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class RequestTrace:
    agent_name: str
    tool_name: str
    session_id: UUID
    request_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ToolObservation:
    stage: str
    agent_name: str
    app_id: UUID
    session_id: UUID
    request_id: UUID
    request_is_active: bool


class SubagentProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self._app = AppTrace()
        self.events: list[str] = []
        self.observations: list[ToolObservation] = []
        self.sessions: dict[str, list[UUID]] = {}
        self.requests: dict[str, list[RequestTrace]] = {}
        self.active_requests: set[UUID] = set()

    @provide(scope=AG2Scope.APP)
    def app_trace(self) -> AppTrace:
        return self._app

    @provide(scope=AG2Scope.SESSION)
    def session_trace(self, context: Context) -> Iterable[SessionTrace]:
        trace = SessionTrace(agent_name=str(context.variables["agent_name"]))
        self.sessions.setdefault(trace.agent_name, []).append(trace.session_id)
        self.events.append(f"session:create:{trace.agent_name}")
        yield trace
        self.events.append(f"session:release:{trace.agent_name}")

    @provide(scope=AG2Scope.REQUEST)
    def request_trace(
        self,
        event: ToolCallEvent,
        session: SessionTrace,
    ) -> Iterable[RequestTrace]:
        trace = RequestTrace(
            agent_name=session.agent_name,
            tool_name=event.name,
            session_id=session.session_id,
        )
        self.requests.setdefault(trace.agent_name, []).append(trace)
        self.active_requests.add(trace.request_id)
        self.events.append(f"request:create:{trace.agent_name}:{trace.tool_name}")
        yield trace
        self.events.append(f"request:release:{trace.agent_name}:{trace.tool_name}")
        self.active_requests.remove(trace.request_id)
