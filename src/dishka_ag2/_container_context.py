from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from autogen.beta.context import Context
from dishka import AsyncContainer, Container

from dishka_ag2._consts import (
    CONTAINER_NAME,
    PENDING_REQUEST_CONTEXT,
    SESSION_CONTAINER_NAME,
)
from dishka_ag2._container import walk_to_scope
from dishka_ag2._scope import AG2Scope
from dishka_ag2._types import ConversationAsyncContainer, ConversationContainer


@asynccontextmanager
async def async_session_scope(
    context: Context,
    context_data: dict[Any, Any],
) -> AsyncIterator[None]:
    previous_current = context.dependencies[CONTAINER_NAME]
    parent: AsyncContainer = previous_current
    async with parent(
        context=context_data,
        scope=AG2Scope.SESSION,
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
    context_data: dict[Any, Any],
) -> Iterator[None]:
    previous_current = context.dependencies[CONTAINER_NAME]
    parent: Container = previous_current
    with parent(
        context=context_data,
        scope=AG2Scope.SESSION,
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
    context_data: dict[Any, Any],
) -> AsyncIterator[None]:
    parent: AsyncContainer = context.dependencies.get(
        SESSION_CONTAINER_NAME,
        root,
    )
    previous_current = context.dependencies[CONTAINER_NAME]
    conversation = walk_to_scope(parent, AG2Scope.CONVERSATION)
    if conversation is not None:
        context_data[ConversationAsyncContainer] = ConversationAsyncContainer(
            conversation
        )
    async with parent(
        context=context_data,
        scope=AG2Scope.REQUEST,
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
    context_data: dict[Any, Any],
) -> Iterator[None]:
    parent: Container = context.dependencies.get(
        SESSION_CONTAINER_NAME,
        root,
    )
    previous_current = context.dependencies[CONTAINER_NAME]
    conversation = walk_to_scope(parent, AG2Scope.CONVERSATION)
    if conversation is not None:
        context_data[ConversationContainer] = ConversationContainer(conversation)

    with parent(
        context=context_data,
        scope=AG2Scope.REQUEST,
    ) as request_container:
        context.dependencies[CONTAINER_NAME] = request_container
        try:
            yield
        finally:
            context.dependencies[CONTAINER_NAME] = previous_current


@contextmanager
def stash_request_context(
    context: Context,
    context_data: dict[Any, Any],
) -> Iterator[None]:
    previous = context.dependencies.get(PENDING_REQUEST_CONTEXT)
    context.dependencies[PENDING_REQUEST_CONTEXT] = context_data
    try:
        yield
    finally:
        if previous is None:
            context.dependencies.pop(PENDING_REQUEST_CONTEXT, None)
        else:
            context.dependencies[PENDING_REQUEST_CONTEXT] = previous
