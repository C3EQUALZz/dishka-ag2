"""Nested Agent.ask() calls with shared CONVERSATION scope."""

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import (
    CONTAINER_NAME,
    AG2Scope,
    ConversationAsyncContainer,
    FromDishka,
    inject,
)
from tests.integration.conftest import async_env
from tests.integration.subagents.common import AppTrace
from tests.integration.subagents.conversation.common import (
    ConversationRequestTrace,
    ConversationSessionTrace,
    ConversationSubagentProvider,
    ConversationTrace,
)


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

        @child_agent.tool
        @inject
        async def child_lookup(
            topic: str,
            app: FromDishka[AppTrace],
            conversation: FromDishka[ConversationTrace],
            session: FromDishka[ConversationSessionTrace],
            request: FromDishka[ConversationRequestTrace],
        ) -> str:
            provider.app_ids.append(app.app_id)
            provider.events.append(
                "tool:child:"
                f"{conversation.conversation_id}:"
                f"{session.session_id}:"
                f"{request.request_id}",
            )
            return f"child ok: {topic}"

        @parent_agent.tool
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
                f"Inspect scopes: {question}",
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

    assert provider.app_ids == [provider._app.app_id]  # noqa: SLF001
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

        @agent.tool
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
