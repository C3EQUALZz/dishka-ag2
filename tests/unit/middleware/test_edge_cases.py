"""Edge-case tests for async and sync middlewares.

Covers:
- Scope cleanup when call_next raises.
- __init__ uses setdefault (respects pre-existing CONTAINER_NAME).
- BaseEvent injection at SESSION scope.
"""

from unittest.mock import Mock

import pytest
from autogen.beta.context import Context
from autogen.beta.events import (
    BaseEvent,
    ModelResponse,
    ToolCallEvent,
)

from dishka_ag2 import FromDishka, inject
from dishka_ag2._consts import CONTAINER_NAME, SESSION_CONTAINER_NAME
from tests.common import AppProvider, RequestDep, SessionDep
from tests.conftest import make_context, make_tool_call
from tests.unit.conftest import create_ag2_env


@pytest.mark.asyncio()
async def test_request_scope_cleanup_on_exception_async(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (root, middleware):
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> None:
            await ctx.dependencies[CONTAINER_NAME].get(RequestDep)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await instance.on_tool_execution(call_next, event, context)

        assert context.dependencies[CONTAINER_NAME] is root
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_request_scope_cleanup_on_exception_sync(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (root, middleware):
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> None:
            ctx.dependencies[CONTAINER_NAME].get(RequestDep)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await instance.on_tool_execution(call_next, event, context)

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
            turn_event: FromDishka[BaseEvent],
        ) -> str:
            captured.append(turn_event)
            return "ok"

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            result: str = await handle(___dishka_context=ctx)  # type: ignore[no-untyped-call]
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
            turn_event: FromDishka[BaseEvent],
        ) -> str:
            captured.append(turn_event)
            return "ok"

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            result: str = handle(___dishka_context=ctx)
            return ModelResponse(message=result)

        await instance.on_turn(turn_body, event, context)

    assert len(captured) == 1
    assert captured[0] is event
