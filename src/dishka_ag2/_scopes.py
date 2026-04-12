from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from autogen.beta.context import Context
from dishka import AsyncContainer, Container, Scope

from dishka_ag2._consts import CONTAINER_NAME, SESSION_CONTAINER_NAME


@asynccontextmanager
async def async_session_scope(
    context: Context,
    root: AsyncContainer,
    context_data: dict[type, Any],
) -> AsyncIterator[None]:
    previous_current = context.dependencies[CONTAINER_NAME]
    async with root(
        context=context_data,
        scope=Scope.SESSION,
    ) as session_container:
        context.dependencies[CONTAINER_NAME] = session_container
        context.dependencies[SESSION_CONTAINER_NAME] = session_container
        try:
            yield
        finally:
            context.dependencies[CONTAINER_NAME] = previous_current
            del context.dependencies[SESSION_CONTAINER_NAME]


@contextmanager
def sync_session_scope(
    context: Context,
    root: Container,
    context_data: dict[type, Any],
) -> Iterator[None]:
    previous_current = context.dependencies[CONTAINER_NAME]
    with root(
        context=context_data,
        scope=Scope.SESSION,
    ) as session_container:
        context.dependencies[CONTAINER_NAME] = session_container
        context.dependencies[SESSION_CONTAINER_NAME] = session_container
        try:
            yield
        finally:
            context.dependencies[CONTAINER_NAME] = previous_current
            del context.dependencies[SESSION_CONTAINER_NAME]


@asynccontextmanager
async def async_request_scope(
    context: Context,
    root: AsyncContainer,
    context_data: dict[type, Any],
) -> AsyncIterator[None]:
    parent: AsyncContainer = context.dependencies.get(
        SESSION_CONTAINER_NAME,
        root,
    )
    previous_current = context.dependencies[CONTAINER_NAME]
    async with parent(
        context=context_data,
        scope=Scope.REQUEST,
    ) as request_container:
        context.dependencies[CONTAINER_NAME] = request_container
        try:
            yield
        finally:
            context.dependencies[CONTAINER_NAME] = previous_current


@contextmanager
def sync_request_scope(
    context: Context,
    root: Container,
    context_data: dict[type, Any],
) -> Iterator[None]:
    parent: Container = context.dependencies.get(
        SESSION_CONTAINER_NAME,
        root,
    )
    previous_current = context.dependencies[CONTAINER_NAME]
    with parent(
        context=context_data,
        scope=Scope.REQUEST,
    ) as request_container:
        context.dependencies[CONTAINER_NAME] = request_container
        try:
            yield
        finally:
            context.dependencies[CONTAINER_NAME] = previous_current
