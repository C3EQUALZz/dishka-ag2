from autogen.beta.context import Context
from dishka import AsyncContainer, Container
from dishka.exception_base import DishkaError

from dishka_ag2._consts import (
    CONTAINER_NAME,
    SESSION_CONTAINER_NAME,
    CurrentContainer,
)


def _get_container_from_context(context: Context) -> CurrentContainer:
    container: CurrentContainer | None = context.dependencies.get(
        CONTAINER_NAME,
    )
    if container is not None:
        return container

    container = context.dependencies.get(SESSION_CONTAINER_NAME)
    if container is not None:
        return container

    msg = (
        "Dishka container not found in Context.dependencies. "
        "Make sure DishkaMiddleware is configured."
    )
    raise DishkaError(msg)


def get_async_container_from_context(context: Context) -> AsyncContainer:
    container = _get_container_from_context(context)
    if not isinstance(container, AsyncContainer):
        msg = "Expected AsyncContainer for async injection."
        raise DishkaError(msg)
    return container


def get_sync_container_from_context(context: Context) -> Container:
    container = _get_container_from_context(context)
    if not isinstance(container, Container):
        msg = (
            "Expected Container for sync injection. "
            "Use AsyncContainer with async tools, or pass a sync Container."
        )
        raise DishkaError(msg)
    return container
