"""Tests for DishkaMiddleware scope lifecycle."""

from unittest.mock import Mock

import pytest
from autogen.beta.context import Context
from autogen.beta.events import (
    BaseEvent,
    ModelResponse,
    ToolCallEvent,
    ToolResultEvent,
)

from dishka_ag2 import FromDishka, inject
from dishka_ag2._consts import CONTAINER_NAME, SESSION_CONTAINER_NAME
from tests.common import (
    APP_DEP_VALUE,
    REQUEST_DEP_VALUE,
    SESSION_DEP_VALUE,
    AppDep,
    AppMock,
    AppProvider,
    RequestDep,
    SessionDep,
)
from tests.conftest import make_context, make_tool_call
from tests.unit.conftest import create_ag2_env

# --- REQUEST scope (on_tool_execution) ---


@pytest.mark.asyncio()
async def test_async_request_dependency(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        async def handle(
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=await handle(___dishka_context=ctx),
            )

        result = await instance.on_tool_execution(
            call_next,
            event,
            context,
        )
        assert result.result.content == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_sync_request_dependency(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        def handle(
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=handle(___dishka_context=ctx),
            )

        result = await instance.on_tool_execution(
            call_next,
            event,
            context,
        )
        assert result.result.content == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_request_scope_per_tool_call(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):

        @inject
        async def handle(
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

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
                    result=await handle(___dishka_context=ctx),
                )

            await instance.on_tool_execution(
                call_next,
                event,
                context,
            )

        assert app_provider.mock.call_count == 2
        assert app_provider.request_released.call_count == 2


@pytest.mark.asyncio()
async def test_request_container_cleanup(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        async def handle(
            request_dep: FromDishka[RequestDep],
        ) -> str:
            return str(request_dep)

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            assert CONTAINER_NAME in ctx.dependencies
            return ToolResultEvent.from_call(
                ev,
                result=await handle(___dishka_context=ctx),
            )

        await instance.on_tool_execution(
            call_next,
            event,
            context,
        )

        assert CONTAINER_NAME not in context.dependencies


# --- APP scope ---


@pytest.mark.asyncio()
async def test_app_dependency(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        async def handle(
            app_dep: FromDishka[AppDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(app_dep)
            return "ok"

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=await handle(___dishka_context=ctx),
            )

        await instance.on_tool_execution(
            call_next,
            event,
            context,
        )

        app_provider.mock.assert_called_with(APP_DEP_VALUE)
        app_provider.app_released.assert_not_called()

    app_provider.app_released.assert_called_once()


@pytest.mark.asyncio()
async def test_app_scope_reuse(
    app_provider: AppProvider,
) -> None:
    app_mocks: list[AppMock] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):

        @inject
        async def handle(
            app_mock: FromDishka[AppMock],
        ) -> str:
            app_mocks.append(app_mock)
            return "ok"

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
                    result=await handle(___dishka_context=ctx),
                )

            await instance.on_tool_execution(
                call_next,
                event,
                context,
            )

    assert len(app_mocks) == 2
    assert app_mocks[0] is app_mocks[1]


# --- SESSION scope (on_turn) ---


@pytest.mark.asyncio()
async def test_session_scope_via_on_turn(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        async def handle(
            session_dep: FromDishka[SessionDep],
        ) -> str:
            return str(session_dep)

        instance = middleware(event, context)

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            result = await handle(___dishka_context=ctx)
            assert result == str(SESSION_DEP_VALUE)
            return ModelResponse(message=result)

        await instance.on_turn(turn_body, event, context)

        app_provider.session_released.assert_called_once()


@pytest.mark.asyncio()
async def test_session_scope_shared_across_tool_calls(
    app_provider: AppProvider,
) -> None:
    session_deps: list[SessionDep] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        async def handle(
            session_dep: FromDishka[SessionDep],
            request_dep: FromDishka[RequestDep],
        ) -> str:
            session_deps.append(session_dep)
            return str(request_dep)

        instance = middleware(event, context)

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            for _ in range(2):
                tool_event = make_tool_call()

                async def call_next(
                    tool_ev: ToolCallEvent,
                    tool_ctx: Context,
                ) -> ToolResultEvent:
                    return ToolResultEvent.from_call(
                        tool_ev,
                        result=await handle(
                            ___dishka_context=tool_ctx,
                        ),
                    )

                await instance.on_tool_execution(
                    call_next,
                    tool_event,
                    ctx,
                )
            return ModelResponse(message="done")

        await instance.on_turn(turn_body, event, context)

    assert len(session_deps) == 2
    assert session_deps[0] is session_deps[1]

    assert app_provider.session_released.call_count == 1
    assert app_provider.request_released.call_count == 2


@pytest.mark.asyncio()
async def test_session_container_cleanup(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            assert SESSION_CONTAINER_NAME in ctx.dependencies
            return ModelResponse(message="ok")

        await instance.on_turn(turn_body, event, context)

        assert SESSION_CONTAINER_NAME not in context.dependencies
