from typing import Final

from autogen.beta.context import Context
from autogen.beta.events import BaseEvent, ModelResponse, ToolCallEvent
from autogen.beta.middleware import (
    AgentTurn,
    BaseMiddleware,
    ToolExecution,
    ToolResultType,
)
from dishka import AsyncContainer, Container, Scope
from dishka.exception_base import DishkaError
from typing_extensions import override

from dishka_ag2._consts import (
    CONTAINER_NAME,
    SESSION_CONTAINER_NAME,
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

    @override
    async def on_turn(
        self,
        call_next: AgentTurn,
        event: BaseEvent,
        context: Context,
    ) -> ModelResponse:
        context_data = {
            BaseEvent: event,
            Context: context,
        }

        async with self._container(
            context=context_data,
            scope=Scope.SESSION,
        ) as session_container:
            context.dependencies[SESSION_CONTAINER_NAME] = session_container
            try:
                return await call_next(event, context)
            finally:
                del context.dependencies[SESSION_CONTAINER_NAME]

    @override
    async def on_tool_execution(
        self,
        call_next: ToolExecution,
        event: ToolCallEvent,
        context: Context,
    ) -> ToolResultType:
        session_container: AsyncContainer | None = context.dependencies.get(
            SESSION_CONTAINER_NAME,
            self._container,
        )
        if session_container is None:
            msg = "Dishka async session container is not configured."
            raise DishkaError(msg)

        context_data = {
            Context: context,
            ToolCallEvent: event,
        }

        async with session_container(
            context=context_data,
            scope=Scope.REQUEST,
        ) as request_container:
            context.dependencies[CONTAINER_NAME] = request_container
            try:
                return await call_next(event, context)
            finally:
                del context.dependencies[CONTAINER_NAME]


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

    @override
    async def on_turn(
        self,
        call_next: AgentTurn,
        event: BaseEvent,
        context: Context,
    ) -> ModelResponse:
        context_data = {
            BaseEvent: event,
            Context: context,
        }

        with self._container(
            context=context_data,
            scope=Scope.SESSION,
        ) as session_container:
            context.dependencies[SESSION_CONTAINER_NAME] = session_container
            try:
                return await call_next(event, context)
            finally:
                del context.dependencies[SESSION_CONTAINER_NAME]

    @override
    async def on_tool_execution(
        self,
        call_next: ToolExecution,
        event: ToolCallEvent,
        context: Context,
    ) -> ToolResultType:
        session_container: Container | None = context.dependencies.get(
            SESSION_CONTAINER_NAME,
            self._container,
        )
        if session_container is None:
            msg = "Dishka sync session container is not configured."
            raise DishkaError(msg)

        context_data = {
            Context: context,
            ToolCallEvent: event,
        }

        with session_container(
            context=context_data,
            scope=Scope.REQUEST,
        ) as request_container:
            context.dependencies[CONTAINER_NAME] = request_container
            try:
                return await call_next(event, context)
            finally:
                del context.dependencies[CONTAINER_NAME]
