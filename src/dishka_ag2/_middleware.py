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
    CurrentContainer,
)


class DishkaMiddleware(BaseMiddleware):  # type: ignore[misc]
    def __init__(
        self,
        event: BaseEvent,
        context: Context,
        *,
        container: CurrentContainer,
    ) -> None:
        super().__init__(event, context)
        self._container: Final[CurrentContainer] = container

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

        if isinstance(self._container, AsyncContainer):
            async with self._container(
                context=context_data,
                scope=Scope.SESSION,
            ) as session_container:
                context.dependencies[SESSION_CONTAINER_NAME] = session_container
                try:
                    return await call_next(event, context)
                finally:
                    del context.dependencies[SESSION_CONTAINER_NAME]
        elif isinstance(self._container, Container):
            with self._container(
                context=context_data,
                scope=Scope.SESSION,
            ) as session_container:
                context.dependencies[SESSION_CONTAINER_NAME] = session_container
                try:
                    return await call_next(event, context)
                finally:
                    del context.dependencies[SESSION_CONTAINER_NAME]

        msg: str = f"Unknown container type - {type(self._container)}"
        raise DishkaError(msg)

    @override
    async def on_tool_execution(
        self,
        call_next: ToolExecution,
        event: ToolCallEvent,
        context: Context,
    ) -> ToolResultType:
        session_container = context.dependencies.get(
            SESSION_CONTAINER_NAME,
            self._container,
        )

        context_data = {
            Context: context,
            ToolCallEvent: event,
        }

        if isinstance(session_container, AsyncContainer):
            async with session_container(
                context=context_data,
                scope=Scope.REQUEST,
            ) as request_container:
                context.dependencies[CONTAINER_NAME] = request_container
                try:
                    return await call_next(event, context)
                finally:
                    del context.dependencies[CONTAINER_NAME]
        elif isinstance(session_container, Container):
            with session_container(
                context=context_data,
                scope=Scope.REQUEST,
            ) as request_container:
                context.dependencies[CONTAINER_NAME] = request_container
                try:
                    return await call_next(event, context)
                finally:
                    del context.dependencies[CONTAINER_NAME]

        msg: str = f"Unknown container type - {type(session_container)}"
        raise DishkaError(msg)
