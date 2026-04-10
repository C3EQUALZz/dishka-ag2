from typing import Final

from autogen.beta.context import Context
from autogen.beta.events import BaseEvent, ToolCallEvent
from autogen.beta.middleware import BaseMiddleware, ToolExecution, ToolResultType
from dishka import AsyncContainer, Container, Scope
from dishka.exception_base import DishkaError

from dishka_autogen._consts import CONTAINER_NAME


class DishkaMiddleware(BaseMiddleware):  # type: ignore[misc]
    def __init__(
        self,
        event: BaseEvent,
        context: Context,
        *,
        container: AsyncContainer | Container,
    ) -> None:
        super().__init__(event, context)
        self._container: Final[AsyncContainer | Container] = container

    async def on_tool_execution(
        self,
        call_next: ToolExecution,
        event: ToolCallEvent,
        context: Context,
    ) -> ToolResultType:
        context_data = {
            Context: context,
            ToolCallEvent: event,
        }

        if isinstance(self._container, AsyncContainer):
            async with self._container(
                context=context_data,
                scope=Scope.REQUEST,
            ) as request_container:
                context.dependencies[CONTAINER_NAME] = request_container
                try:
                    return await call_next(event, context)
                finally:
                    del context.dependencies[CONTAINER_NAME]
        elif isinstance(self._container, Container):
            with self._container(
                context=context_data,
                scope=Scope.REQUEST,
            ) as request_container:
                context.dependencies[CONTAINER_NAME] = request_container
                try:
                    return await call_next(event, context)
                finally:
                    del context.dependencies[CONTAINER_NAME]

        msg: str = f"Unknown container type - {type(self._container)}"
        raise DishkaError(msg)
