"""Tests for error handling and container type mismatch."""

import pytest
from autogen.beta.context import Context
from autogen.beta.events import ToolCallEvent, ToolResultEvent
from dishka.exception_base import DishkaError

from dishka_ag2 import FromDishka, inject
from tests.common import AppDep, AppProvider
from tests.conftest import make_context, make_tool_call
from tests.unit.conftest import create_ag2_env


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
            app_dep: FromDishka[AppDep],
        ) -> str:
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
                result=await handle(___dishka_context=ctx),
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
            app_dep: FromDishka[AppDep],
        ) -> str:
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
                result=handle(___dishka_context=ctx),
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
        app_dep: FromDishka[AppDep],
    ) -> str:
        return str(app_dep)

    context = make_context()

    with pytest.raises((DishkaError, KeyError)):
        await handle(___dishka_context=context)
