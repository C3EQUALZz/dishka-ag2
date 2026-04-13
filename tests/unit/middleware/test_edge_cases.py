"""Edge-case tests for async and sync middlewares.

Covers:
- Scope cleanup when call_next raises.
- __init__ uses setdefault (respects pre-existing CONTAINER_NAME).
- BaseEvent injection at SESSION scope.
"""

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from autogen.beta.context import Context
from autogen.beta.events import (
    BaseEvent,
    ModelResponse,
)

from dishka_ag2 import FromDishka, inject
from dishka_ag2._consts import CONTAINER_NAME, SESSION_CONTAINER_NAME
from tests.common import AppProvider, RequestDep, SessionDep
from tests.conftest import make_context, make_tool_call
from tests.unit.conftest import create_ag2_env

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@pytest.mark.asyncio()
async def test_inject_request_cleanup_on_exception_async(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (root, middleware):
        context = make_context()
        event = make_tool_call()
        middleware(event, context)

        @inject
        async def handle(
            ctx: Context,
            request_dep: FromDishka[RequestDep],
        ) -> None:
            _ = (ctx, request_dep)
            raise RuntimeError("boom")

        typed_handle: Callable[[Context], Awaitable[None]] = handle

        with pytest.raises(RuntimeError, match="boom"):
            await typed_handle(context)

        assert context.dependencies[CONTAINER_NAME] is root
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_inject_request_cleanup_on_exception_sync(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (root, middleware):
        context = make_context()
        event = make_tool_call()
        middleware(event, context)

        @inject
        def handle(
            ctx: Context,
            request_dep: FromDishka[RequestDep],
        ) -> None:
            _ = (ctx, request_dep)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            handle(context)

        assert context.dependencies[CONTAINER_NAME] is root
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_session_scope_cleanup_on_exception_async(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (root, middleware):
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> None:
            await ctx.dependencies[CONTAINER_NAME].get(SessionDep)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await instance.on_turn(turn_body, event, context)

        assert context.dependencies[CONTAINER_NAME] is root
        assert SESSION_CONTAINER_NAME not in context.dependencies
        app_provider.session_released.assert_called_once()


@pytest.mark.asyncio()
async def test_session_scope_cleanup_on_exception_sync(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (root, middleware):
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> None:
            ctx.dependencies[CONTAINER_NAME].get(SessionDep)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await instance.on_turn(turn_body, event, context)

        assert context.dependencies[CONTAINER_NAME] is root
        assert SESSION_CONTAINER_NAME not in context.dependencies
        app_provider.session_released.assert_called_once()


@pytest.mark.asyncio()
async def test_init_preserves_existing_container_async(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (root, middleware):
        user_container = Mock()
        context = make_context()
        context.dependencies[CONTAINER_NAME] = user_container
        event = make_tool_call()

        middleware(event, context)

        assert context.dependencies[CONTAINER_NAME] is user_container
        assert context.dependencies[CONTAINER_NAME] is not root


@pytest.mark.asyncio()
async def test_init_preserves_existing_container_sync(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (root, middleware):
        user_container = Mock()
        context = make_context()
        context.dependencies[CONTAINER_NAME] = user_container
        event = make_tool_call()

        middleware(event, context)

        assert context.dependencies[CONTAINER_NAME] is user_container
        assert context.dependencies[CONTAINER_NAME] is not root


@pytest.mark.asyncio()
async def test_base_event_injected_at_session_async(
    app_provider: AppProvider,
) -> None:
    captured: list[BaseEvent] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call("session_event")
        instance = middleware(event, context)

        @inject
        async def handle(
            ctx: Context,
            turn_event: FromDishka[BaseEvent],
        ) -> str:
            _ = ctx
            captured.append(turn_event)
            return "ok"

        typed_handle: Callable[[Context], Awaitable[str]] = handle

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            result: str = await typed_handle(ctx)
            return ModelResponse(message=result)

        await instance.on_turn(turn_body, event, context)

    assert len(captured) == 1
    assert captured[0] is event


@pytest.mark.asyncio()
async def test_base_event_injected_at_session_sync(
    app_provider: AppProvider,
) -> None:
    captured: list[BaseEvent] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call("session_event")
        instance = middleware(event, context)

        @inject
        def handle(
            ctx: Context,
            turn_event: FromDishka[BaseEvent],
        ) -> str:
            _ = ctx
            captured.append(turn_event)
            return "ok"

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            result = handle(ctx)
            return ModelResponse(message=result)

        await instance.on_turn(turn_body, event, context)

    assert len(captured) == 1
    assert captured[0] is event
