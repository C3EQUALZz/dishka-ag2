"""CONVERSATION scope handle injection with sync Dishka container."""

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig

from dishka_ag2 import (
    CONTAINER_NAME,
    AG2Scope,
    ConversationContainer,
    FromDishka,
    inject,
)
from tests.integration.conftest import sync_env
from tests.integration.subagents.conversation.common import (
    ConversationProvider,
    ConversationTrace,
)


@pytest.mark.asyncio()
async def test_sync_tool_can_receive_conversation_container() -> None:
    provider = ConversationProvider()
    injected_containers: list[ConversationContainer] = []

    async with sync_env(provider) as (container, middleware):
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
        def check(
            conversation_container: FromDishka[ConversationContainer],
            conversation: FromDishka[ConversationTrace],
        ) -> str:
            injected_containers.append(conversation_container)
            return str(conversation.conversation_id)

        with container(scope=AG2Scope.CONVERSATION) as conversation_container:
            await agent.ask(
                "Check scopes.",
                dependencies={CONTAINER_NAME: conversation_container},
            )

        assert injected_containers == [conversation_container]
        assert len(provider.conversations) == 1


@pytest.mark.asyncio()
async def test_sync_tool_can_receive_only_conversation_container() -> None:
    injected_containers: list[ConversationContainer] = []

    async with sync_env() as (container, middleware):
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
        def check(
            conversation_container: FromDishka[ConversationContainer],
        ) -> str:
            injected_containers.append(conversation_container)
            return "ok"

        with container(scope=AG2Scope.CONVERSATION) as conversation_container:
            await agent.ask(
                "Check scopes.",
                dependencies={CONTAINER_NAME: conversation_container},
            )

        assert injected_containers == [conversation_container]
