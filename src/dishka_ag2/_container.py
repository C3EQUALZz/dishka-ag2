from dishka import AsyncContainer, Container
from dishka.exception_base import DishkaError

from dishka_ag2._compat import Context
from dishka_ag2._consts import CONTAINER_NAME
from dishka_ag2._scope import AG2Scope
from dishka_ag2._types import ContainerT


def _get_container_from_context(
    context: Context,
    container_type: type[ContainerT],
) -> ContainerT:
    try:
        container = context.dependencies[CONTAINER_NAME]
    except KeyError as e:
        msg = (
            "Dishka container not found in AG2 context dependencies. "
            "Make sure DishkaAsyncMiddleware or DishkaSyncMiddleware is configured."
        )
        raise DishkaError(msg) from e

    if not isinstance(container, container_type):
        msg = f"Expected {container_type.__name__}"
        raise DishkaError(msg)
    return container


def get_async_container_from_context(context: Context) -> AsyncContainer:
    return _get_container_from_context(context, AsyncContainer)


def get_sync_container_from_context(context: Context) -> Container:
    return _get_container_from_context(context, Container)


def walk_to_scope(container: ContainerT, scope: AG2Scope) -> ContainerT | None:
    current: ContainerT | None = container
    while current is not None:
        if current.scope is scope:
            return current
        current = current.parent_container
    return None


def walk_to_root(container: ContainerT) -> ContainerT:
    current = container
    while current.scope is not AG2Scope.APP and current.parent_container is not None:
        current = current.parent_container
    return current
