"""Mixed child tools sharing the parent's explicit CONVERSATION."""

import pytest
from ag2 import Agent
from ag2.events import ToolCallEvent
from ag2.testing import TestConfig

from dishka_ag2 import (
    CONTAINER_NAME,
    AG2Scope,
    ConversationAsyncContainer,
    FromDishka,
    inject,
)
from tests.integration.conftest import async_env
from tests.integration.subagents.conversation.common import (
    ConversationRequestTrace,
    ConversationSessionTrace,
    ConversationSubagentProvider,
    ConversationTrace,
)


@pytest.mark.asyncio()
async def test_mixed_tools_share_conversation_across_agents() -> None:
    provider = ConversationSubagentProvider()
    conversations: list[ConversationTrace] = []
    containers: list[ConversationAsyncContainer] = []

    async with async_env(provider) as (root, middleware):
        child = Agent(
            "child",
            config=TestConfig(
                ToolCallEvent(name="sync_lookup", arguments="{}"),
                ToolCallEvent(name="async_lookup", arguments="{}"),
                "Child finished.",
            ),
            variables={"agent_name": "child"},
            middleware=[middleware],
        )
        parent = Agent(
            "parent",
            config=TestConfig(
                ToolCallEvent(name="ask_child", arguments="{}"),
                "Parent finished.",
            ),
            variables={"agent_name": "parent"},
            middleware=[middleware],
        )

        @child.tool
        @inject
        def sync_lookup(
            conversation: FromDishka[ConversationTrace],
            container: FromDishka[ConversationAsyncContainer],
            session: FromDishka[ConversationSessionTrace],
            request: FromDishka[ConversationRequestTrace],
        ) -> str:
            assert session.agent_name == "child"
            assert request.tool_name == "sync_lookup"
            conversations.append(conversation)
            containers.append(container)
            return "sync result"

        @child.tool
        @inject
        async def async_lookup(
            conversation: FromDishka[ConversationTrace],
            container: FromDishka[ConversationAsyncContainer],
            session: FromDishka[ConversationSessionTrace],
            request: FromDishka[ConversationRequestTrace],
        ) -> str:
            assert session.agent_name == "child"
            assert request.tool_name == "async_lookup"
            conversations.append(conversation)
            containers.append(container)
            return "async result"

        @parent.tool
        @inject
        async def ask_child(
            conversation: FromDishka[ConversationTrace],
            container: FromDishka[ConversationAsyncContainer],
            session: FromDishka[ConversationSessionTrace],
            request: FromDishka[ConversationRequestTrace],
        ) -> str:
            assert session.agent_name == "parent"
            assert request.tool_name == "ask_child"
            conversations.append(conversation)
            containers.append(container)
            reply = await child.ask(
                "Run both tools.",
                dependencies={CONTAINER_NAME: container},
            )
            return str(reply.body)

        async with root(scope=AG2Scope.CONVERSATION) as conversation_container:
            await parent.ask(
                "Ask the child to run both tools.",
                dependencies={CONTAINER_NAME: conversation_container},
            )
            assert containers == [conversation_container] * 3

    assert len(conversations) == 3
    assert all(conversation is conversations[0] for conversation in conversations)
    assert provider.conversations == [conversations[0].conversation_id]
    parent_session = provider.sessions["parent"][0]
    child_session = provider.sessions["child"][0]
    assert parent_session.session_id != child_session.session_id
    child_requests = provider.requests["child"]
    assert len(child_requests) == 2
    assert child_requests[0].request_id != child_requests[1].request_id
    assert all(
        request.session_id == child_session.session_id for request in child_requests
    )
    assert all(
        request.conversation_id == conversations[0].conversation_id
        for request in child_requests
    )
    assert provider.events[0] == "conversation:create"
    assert provider.events[-1] == "conversation:release"
    assert provider.events.index("session:release:child") < provider.events.index(
        "request:release:parent:ask_child",
    )
