from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Final

from autogen.beta.context import Context
from dishka import AsyncContainer, Container, Scope
from dishka.exception_base import DishkaError

from dishka_ag2._consts import (
    CONTAINER_NAME,
    SESSION_CONTAINER_NAME,
)

_SENTINEL: Final[object] = object()


@asynccontextmanager
async def async_session_scope(
    context: Context,
    root: AsyncContainer,
    context_data: dict[type, Any],
) -> AsyncIterator[None]:
    async with root(
        context=context_data,
        scope=Scope.SESSION,
    ) as session_container:
        context.dependencies[SESSION_CONTAINER_NAME] = session_container
        try:
            yield
        finally:
            del context.dependencies[SESSION_CONTAINER_NAME]


@contextmanager
def sync_session_scope(
    context: Context,
    root: Container,
    context_data: dict[type, Any],
) -> Iterator[None]:
    with root(
        context=context_data,
        scope=Scope.SESSION,
    ) as session_container:
        context.dependencies[SESSION_CONTAINER_NAME] = session_container
        try:
            yield
        finally:
            del context.dependencies[SESSION_CONTAINER_NAME]


@asynccontextmanager
async def async_request_scope(
    context: Context,
    root: AsyncContainer,
    context_data: dict[type, Any],
) -> AsyncIterator[None]:
    parent: AsyncContainer | None = context.dependencies.get(
        SESSION_CONTAINER_NAME,
        root,
    )
    if parent is None:
        msg = "Dishka async session container is not configured."
        raise DishkaError(msg)

    previous = context.dependencies.get(CONTAINER_NAME, _SENTINEL)
    async with parent(
        context=context_data,
        scope=Scope.REQUEST,
    ) as request_container:
        context.dependencies[CONTAINER_NAME] = request_container
        try:
            yield
        finally:
            if previous is _SENTINEL:
                context.dependencies.pop(CONTAINER_NAME, None)
            else:
                context.dependencies[CONTAINER_NAME] = previous


@contextmanager
def sync_request_scope(
    context: Context,
    root: Container,
    context_data: dict[type, Any],
) -> Iterator[None]:
    parent: Container | None = context.dependencies.get(
        SESSION_CONTAINER_NAME,
        root,
    )
    if parent is None:
        msg = "Dishka sync session container is not configured."
        raise DishkaError(msg)

    previous = context.dependencies.get(CONTAINER_NAME, _SENTINEL)
    with parent(
        context=context_data,
        scope=Scope.REQUEST,
    ) as request_container:
        context.dependencies[CONTAINER_NAME] = request_container
        try:
            yield
        finally:
            if previous is _SENTINEL:
                context.dependencies.pop(CONTAINER_NAME, None)
            else:
                context.dependencies[CONTAINER_NAME] = previous
