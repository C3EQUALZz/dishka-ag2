"""Nested Agent.ask() calls with async Dishka container."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from autogen.beta import Agent
from autogen.beta.annotations import Context
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from dishka import Provider, provide

from dishka_ag2 import (
    CONTAINER_NAME,
    AG2Scope,
    ConversationAsyncContainer,
    FromDishka,
    inject,
)
from tests.integration.conftest import async_env


@dataclass(frozen=True)
class AppTrace:
    app_id: UUID = field(default_factory=uuid4)


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


class ConversationSubagentProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []
        self.conversations: list[UUID] = []
        self.sessions: dict[str, list[ConversationSessionTrace]] = {}
        self.requests: dict[str, list[ConversationRequestTrace]] = {}

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


@pytest.mark.asyncio()
async def test_nested_agent_ask_uses_separate_session_and_request() -> None:
    provider = SubagentProvider()

    async with async_env(provider) as (_, middleware):
        child_agent = Agent(
            "child",
            config=TestConfig(
                ToolCallEvent(
                    name="child_lookup",
                    arguments='{"topic": "scopes"}',
                ),
                "Child finished.",
            ),
            middleware=[middleware],
            variables={"agent_name": "child"},
        )
        parent_agent = Agent(
            "parent",
            config=TestConfig(
                ToolCallEvent(
                    name="ask_child",
                    arguments='{"question": "Check scopes"}',
                ),
                "Parent finished.",
            ),
            middleware=[middleware],
            variables={"agent_name": "parent"},
        )

        @child_agent.tool  # type: ignore[untyped-decorator]
        @inject
        async def child_lookup(
            topic: str,
            app: FromDishka[AppTrace],
            session: FromDishka[SessionTrace],
            request: FromDishka[RequestTrace],
        ) -> str:
            provider.events.append("tool:child")
            provider.observations.append(
                ToolObservation(
                    stage=f"child:{topic}",
                    agent_name=session.agent_name,
                    app_id=app.app_id,
                    session_id=session.session_id,
                    request_id=request.request_id,
                    request_is_active=request.request_id in provider.active_requests,
                ),
            )
            return "child ok"

        @parent_agent.tool  # type: ignore[untyped-decorator]
        @inject
        async def ask_child(
            question: str,
            app: FromDishka[AppTrace],
            session: FromDishka[SessionTrace],
            request: FromDishka[RequestTrace],
        ) -> str:
            provider.events.append("tool:parent:before-child")
            provider.observations.append(
                ToolObservation(
                    stage=f"parent:before:{question}",
                    agent_name=session.agent_name,
                    app_id=app.app_id,
                    session_id=session.session_id,
                    request_id=request.request_id,
                    request_is_active=request.request_id in provider.active_requests,
                ),
            )

            reply = await child_agent.ask("Inspect scopes.")

            provider.events.append("tool:parent:after-child")
            provider.observations.append(
                ToolObservation(
                    stage=f"parent:after:{reply.body}",
                    agent_name=session.agent_name,
                    app_id=app.app_id,
                    session_id=session.session_id,
                    request_id=request.request_id,
                    request_is_active=request.request_id in provider.active_requests,
                ),
            )
            return str(reply.body)

        await parent_agent.ask("Ask child.")

    parent_session = provider.sessions["parent"][0]
    child_session = provider.sessions["child"][0]
    parent_request = provider.requests["parent"][0]
    child_request = provider.requests["child"][0]

    assert parent_session != child_session
    assert parent_request.session_id == parent_session
    assert child_request.session_id == child_session
    assert parent_request.request_id != child_request.request_id
    assert parent_request.tool_name == "ask_child"
    assert child_request.tool_name == "child_lookup"

    assert {observation.app_id for observation in provider.observations} == {
        provider._app.app_id,  # noqa: SLF001
    }
    assert [observation.agent_name for observation in provider.observations] == [
        "parent",
        "child",
        "parent",
    ]
    assert [observation.session_id for observation in provider.observations] == [
        parent_session,
        child_session,
        parent_session,
    ]
    assert [observation.request_id for observation in provider.observations] == [
        parent_request.request_id,
        child_request.request_id,
        parent_request.request_id,
    ]
    assert all(observation.request_is_active for observation in provider.observations)

    assert provider.events == [
        "session:create:parent",
        "request:create:parent:ask_child",
        "tool:parent:before-child",
        "session:create:child",
        "request:create:child:child_lookup",
        "tool:child",
        "request:release:child:child_lookup",
        "session:release:child",
        "tool:parent:after-child",
        "request:release:parent:ask_child",
        "session:release:parent",
    ]


@pytest.mark.asyncio()
async def test_nested_agent_ask_can_share_explicit_conversation_scope() -> None:
    provider = ConversationSubagentProvider()
    injected_conversation_containers: list[ConversationAsyncContainer] = []

    async with async_env(provider) as (container, middleware):
        child_agent = Agent(
            "child",
            config=TestConfig(
                ToolCallEvent(
                    name="child_lookup",
                    arguments='{"topic": "scopes"}',
                ),
                "Child finished.",
            ),
            middleware=[middleware],
            variables={"agent_name": "child"},
        )
        parent_agent = Agent(
            "parent",
            config=TestConfig(
                ToolCallEvent(
                    name="ask_child",
                    arguments='{"question": "Check scopes"}',
                ),
                "Parent finished.",
            ),
            middleware=[middleware],
            variables={"agent_name": "parent"},
        )

        @child_agent.tool  # type: ignore[untyped-decorator]
        @inject
        async def child_lookup(
            topic: str,
            conversation: FromDishka[ConversationTrace],
            session: FromDishka[ConversationSessionTrace],
            request: FromDishka[ConversationRequestTrace],
        ) -> str:
            provider.events.append(
                "tool:child:"
                f"{conversation.conversation_id}:"
                f"{session.session_id}:"
                f"{request.request_id}",
            )
            return "child ok"

        @parent_agent.tool  # type: ignore[untyped-decorator]
        @inject
        async def ask_child(
            question: str,
            conversation_container: FromDishka[ConversationAsyncContainer],
            conversation: FromDishka[ConversationTrace],
            session: FromDishka[ConversationSessionTrace],
            request: FromDishka[ConversationRequestTrace],
        ) -> str:
            injected_conversation_containers.append(conversation_container)
            provider.events.append(
                "tool:parent:before-child:"
                f"{conversation.conversation_id}:"
                f"{session.session_id}:"
                f"{request.request_id}",
            )

            reply = await child_agent.ask(
                "Inspect scopes.",
                dependencies={CONTAINER_NAME: conversation_container},
            )

            provider.events.append("tool:parent:after-child")
            return str(reply.body)

        async with container(scope=AG2Scope.CONVERSATION) as conversation_container:
            await parent_agent.ask(
                "Ask child.",
                dependencies={CONTAINER_NAME: conversation_container},
            )

        assert injected_conversation_containers == [conversation_container]

    parent_session = provider.sessions["parent"][0]
    child_session = provider.sessions["child"][0]
    parent_request = provider.requests["parent"][0]
    child_request = provider.requests["child"][0]
    conversation_id = provider.conversations[0]

    assert provider.conversations == [conversation_id]
    assert parent_session.conversation_id == conversation_id
    assert child_session.conversation_id == conversation_id
    assert parent_session.session_id != child_session.session_id
    assert parent_request.conversation_id == conversation_id
    assert child_request.conversation_id == conversation_id
    assert parent_request.session_id == parent_session.session_id
    assert child_request.session_id == child_session.session_id
    assert parent_request.request_id != child_request.request_id
    assert parent_request.tool_name == "ask_child"
    assert child_request.tool_name == "child_lookup"

    assert provider.events[0] == "conversation:create"
    assert provider.events[-1] == "conversation:release"
    assert provider.events[1:5] == [
        "session:create:parent",
        "request:create:parent:ask_child",
        (
            "tool:parent:before-child:"
            f"{conversation_id}:"
            f"{parent_session.session_id}:"
            f"{parent_request.request_id}"
        ),
        "session:create:child",
    ]
    assert provider.events[6] == (
        "tool:child:"
        f"{conversation_id}:"
        f"{child_session.session_id}:"
        f"{child_request.request_id}"
    )


@pytest.mark.asyncio()
async def test_async_tool_can_receive_only_conversation_container() -> None:
    injected_containers: list[ConversationAsyncContainer] = []

    async with async_env() as (container, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="check", arguments="{}"),
                "Done.",
            ),
            middleware=[middleware],
        )

        @agent.tool  # type: ignore[untyped-decorator]
        @inject
        async def check(
            conversation_container: FromDishka[ConversationAsyncContainer],
        ) -> str:
            injected_containers.append(conversation_container)
            return "ok"

        async with container(scope=AG2Scope.CONVERSATION) as conversation_container:
            await agent.ask(
                "Check scopes.",
                dependencies={CONTAINER_NAME: conversation_container},
            )

        assert injected_containers == [conversation_container]
