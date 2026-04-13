"""APP scope lifecycle tests for DishkaAsyncMiddleware."""

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from autogen.beta.context import Context
from autogen.beta.events import ToolCallEvent, ToolResultEvent

from dishka_ag2 import FromDishka, inject
from tests.common import APP_DEP_VALUE, AppDep, AppMock, AppProvider
from tests.conftest import make_context, make_tool_call
from tests.unit.conftest import create_ag2_env

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


@pytest.mark.asyncio()
async def test_app_dependency(app_provider: AppProvider) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        async def handle(
            ctx: Context,
            app_dep: FromDishka[AppDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(app_dep)
            return "ok"

        typed_handle: Callable[[Context], Awaitable[str]] = handle
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=await typed_handle(ctx),
            )

        await instance.on_tool_execution(call_next, event, context)

        app_provider.mock.assert_called_with(APP_DEP_VALUE)
        app_provider.app_released.assert_not_called()

    app_provider.app_released.assert_called_once()


@pytest.mark.asyncio()
async def test_app_scope_reuse(app_provider: AppProvider) -> None:
    app_mocks: list[AppMock] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):

        @inject
        async def handle(
            ctx: Context,
            app_mock: FromDishka[AppMock],
        ) -> str:
            _ = ctx
            app_mocks.append(app_mock)
            return "ok"

        typed_handle: Callable[[Context], Awaitable[str]] = handle

        for _ in range(2):
            context = make_context()
            event = make_tool_call()
            instance = middleware(event, context)

            async def call_next(
                ev: ToolCallEvent,
                ctx: Context,
            ) -> ToolResultEvent:
                return ToolResultEvent.from_call(
                    ev,
                    result=await typed_handle(ctx),
                )

            await instance.on_tool_execution(call_next, event, context)

    assert len(app_mocks) == 2
    assert app_mocks[0] is app_mocks[1]
