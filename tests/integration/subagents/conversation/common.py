from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from autogen.beta.annotations import Context
from autogen.beta.events import ToolCallEvent
from dishka import Provider, provide

from dishka_ag2 import AG2Scope
from tests.integration.subagents.common import AppTrace


@dataclass(frozen=True)
class ConversationTrace:
    conversation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ConversationSessionTrace:
    agent_name: str
    conversation_id: UUID
    session_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ConversationRequestTrace:
    agent_name: str
    tool_name: str
    conversation_id: UUID
    session_id: UUID
    request_id: UUID = field(default_factory=uuid4)


class ConversationProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.conversations: list[UUID] = []

    @provide(scope=AG2Scope.CONVERSATION)
    def conversation_trace(self) -> Iterable[ConversationTrace]:
        trace = ConversationTrace()
        self.conversations.append(trace.conversation_id)
        yield trace


class ConversationSubagentProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self._app = AppTrace()
        self.events: list[str] = []
        self.conversations: list[UUID] = []
        self.sessions: dict[str, list[ConversationSessionTrace]] = {}
        self.requests: dict[str, list[ConversationRequestTrace]] = {}
        self.app_ids: list[UUID] = []

    @provide(scope=AG2Scope.APP)
    def app_trace(self) -> AppTrace:
        return self._app

    @provide(scope=AG2Scope.CONVERSATION)
    def conversation_trace(self) -> Iterable[ConversationTrace]:
        trace = ConversationTrace()
        self.conversations.append(trace.conversation_id)
        self.events.append("conversation:create")
        yield trace
        self.events.append("conversation:release")

    @provide(scope=AG2Scope.SESSION)
    def session_trace(
        self,
        context: Context,
        conversation: ConversationTrace,
    ) -> Iterable[ConversationSessionTrace]:
        trace = ConversationSessionTrace(
            agent_name=str(context.variables["agent_name"]),
            conversation_id=conversation.conversation_id,
        )
        self.sessions.setdefault(trace.agent_name, []).append(trace)
        self.events.append(f"session:create:{trace.agent_name}")
        yield trace
        self.events.append(f"session:release:{trace.agent_name}")

    @provide(scope=AG2Scope.REQUEST)
    def request_trace(
        self,
        event: ToolCallEvent,
        session: ConversationSessionTrace,
    ) -> Iterable[ConversationRequestTrace]:
        trace = ConversationRequestTrace(
            agent_name=session.agent_name,
            tool_name=event.name,
            conversation_id=session.conversation_id,
            session_id=session.session_id,
        )
        self.requests.setdefault(trace.agent_name, []).append(trace)
        self.events.append(f"request:create:{trace.agent_name}:{trace.tool_name}")
        yield trace
        self.events.append(f"request:release:{trace.agent_name}:{trace.tool_name}")
