"""Tests for error handling and container type mismatch."""

from typing import TYPE_CHECKING

import pytest
from autogen.beta.events import ToolCallEvent, ToolResultEvent
from dishka.exception_base import DishkaError

from dishka_ag2 import FromDishka, inject
from dishka_ag2._compat import Context
from tests.common import AppDep, AppProvider
from tests.conftest import make_context, make_tool_call
from tests.unit.conftest import create_ag2_env

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@pytest.mark.asyncio()
async def test_async_tool_with_sync_container_raises(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):

        @inject
        async def handle(
            ctx: Context,
            app_dep: FromDishka[AppDep],
        ) -> str:
            _ = ctx
            return str(app_dep)

        typed_handle: Callable[[Context], Awaitable[str]] = handle
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            result: str = await typed_handle(ctx)

            return ToolResultEvent.from_call(
                ev,
                result=result,
            )

        with pytest.raises(
            DishkaError,
            match="Expected AsyncContainer",
        ):
            await instance.on_tool_execution(
                call_next,
                event,
                context,
            )


@pytest.mark.asyncio()
async def test_sync_tool_with_async_container_raises(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):

        @inject
        def handle(
            ctx: Context,
            app_dep: FromDishka[AppDep],
        ) -> str:
            _ = ctx
            return str(app_dep)

        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=handle(ctx),
            )

        with pytest.raises(
            DishkaError,
            match="Expected Container",
        ):
            await instance.on_tool_execution(
                call_next,
                event,
                context,
            )


@pytest.mark.asyncio()
async def test_missing_middleware_raises() -> None:
    @inject
    async def handle(
        ctx: Context,
        app_dep: FromDishka[AppDep],
    ) -> str:
        _ = ctx
        return str(app_dep)

    typed_handle: Callable[[Context], Awaitable[str]] = handle
    context = make_context()

    with pytest.raises((DishkaError, KeyError)):
        await typed_handle(context)
