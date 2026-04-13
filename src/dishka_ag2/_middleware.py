from collections.abc import Sequence
from typing import Final

from autogen.beta.context import Context
from autogen.beta.events import (
    BaseEvent,
    HumanInputRequest,
    HumanMessage,
    ModelResponse,
    ToolCallEvent,
)
from autogen.beta.middleware import (
    AgentTurn,
    BaseMiddleware,
    HumanInputHook,
    LLMCall,
    ToolExecution,
    ToolResultType,
)
from dishka import AsyncContainer, Container
from typing_extensions import override

from dishka_ag2._consts import CONTAINER_NAME
from dishka_ag2._scopes import (
    async_session_scope,
    stash_request_context,
    sync_session_scope,
)


class DishkaAsyncMiddleware(BaseMiddleware):  # type: ignore[misc]
    def __init__(
        self,
        event: BaseEvent,
        context: Context,
        *,
        container: AsyncContainer,
    ) -> None:
        super().__init__(event, context)
        self._container: Final[AsyncContainer] = container
        context.dependencies.setdefault(CONTAINER_NAME, container)

    @override
    async def on_turn(
        self,
        call_next: AgentTurn,
        event: BaseEvent,
        context: Context,
    ) -> ModelResponse:
        context_data = {BaseEvent: event, Context: context}

        async with async_session_scope(context, self._container, context_data):
            return await call_next(event, context)

    @override
    async def on_tool_execution(
        self,
        call_next: ToolExecution,
        event: ToolCallEvent,
        context: Context,
    ) -> ToolResultType:
        context_data = {Context: context, ToolCallEvent: event}

        with stash_request_context(context, context_data):
            return await call_next(event, context)

    @override
    async def on_llm_call(
        self,
        call_next: LLMCall,
        events: Sequence[BaseEvent],
        context: Context,
    ) -> ModelResponse:
        context_data = {Context: context}

        with stash_request_context(context, context_data):
            return await call_next(events, context)

    @override
    async def on_human_input(
        self,
        call_next: HumanInputHook,
        event: HumanInputRequest,
        context: Context,
    ) -> HumanMessage:
        context_data = {Context: context, HumanInputRequest: event}

        with stash_request_context(context, context_data):
            return await call_next(event, context)


class DishkaSyncMiddleware(BaseMiddleware):  # type: ignore[misc]
    def __init__(
        self,
        event: BaseEvent,
        context: Context,
        *,
        container: Container,
    ) -> None:
        super().__init__(event, context)
        self._container: Final[Container] = container
        context.dependencies.setdefault(CONTAINER_NAME, container)

    @override
    async def on_turn(
        self,
        call_next: AgentTurn,
        event: BaseEvent,
        context: Context,
    ) -> ModelResponse:
        context_data = {BaseEvent: event, Context: context}

        with sync_session_scope(context, self._container, context_data):
            return await call_next(event, context)

    @override
    async def on_tool_execution(
        self,
        call_next: ToolExecution,
        event: ToolCallEvent,
        context: Context,
    ) -> ToolResultType:
        context_data = {Context: context, ToolCallEvent: event}

        with stash_request_context(context, context_data):
            return await call_next(event, context)

    @override
    async def on_llm_call(
        self,
        call_next: LLMCall,
        events: Sequence[BaseEvent],
        context: Context,
    ) -> ModelResponse:
        context_data = {Context: context}

        with stash_request_context(context, context_data):
            return await call_next(events, context)

    @override
    async def on_human_input(
        self,
        call_next: HumanInputHook,
        event: HumanInputRequest,
        context: Context,
    ) -> HumanMessage:
        context_data = {Context: context, HumanInputRequest: event}

        with stash_request_context(context, context_data):
            return await call_next(event, context)
