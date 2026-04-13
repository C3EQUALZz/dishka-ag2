"""REQUEST scope tests for DishkaAsyncMiddleware."""

from collections.abc import Awaitable, Callable, Sequence
from unittest.mock import Mock

import pytest
from autogen.beta.context import Context
from autogen.beta.events import (
    BaseEvent,
    HumanInputRequest,
    HumanMessage,
    ModelResponse,
    ToolCallEvent,
    ToolResultEvent,
)
from dishka.exception_base import DishkaError

from dishka_ag2 import FromDishka, inject
from dishka_ag2._consts import CONTAINER_NAME, PENDING_REQUEST_CONTEXT
from tests.common import REQUEST_DEP_VALUE, AppProvider, RequestDep
from tests.conftest import (
    make_context,
    make_human_input_request,
    make_llm_events,
    make_tool_call,
)
from tests.unit.conftest import create_ag2_env


@pytest.mark.asyncio()
async def test_request_dependency(app_provider: AppProvider) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        async def handle(
            ctx: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

        typed_handle: Callable[[Context], Awaitable[str]] = handle
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            res: str = await typed_handle(ctx)

            return ToolResultEvent.from_call(
                ev,
                result=res,
            )

        result = await instance.on_tool_execution(call_next, event, context)
        assert result.result.content == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_injection_uses_positional_context(
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
            context: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return str(context.variables)

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

        result = await instance.on_tool_execution(call_next, event, context)
        assert result.result.content == "{}"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)


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
            ctx: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
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

        assert app_provider.mock.call_count == 2
        assert app_provider.request_released.call_count == 2


@pytest.mark.asyncio()
async def test_tool_execution_stashes_and_clears_pending_context(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            pending = ctx.dependencies[PENDING_REQUEST_CONTEXT]
            assert pending[Context] is ctx
            assert pending[ToolCallEvent] is ev
            return ToolResultEvent.from_call(ev, result="ok")

        await instance.on_tool_execution(call_next, event, context)
        assert PENDING_REQUEST_CONTEXT not in context.dependencies


@pytest.mark.asyncio()
async def test_missing_container_raises() -> None:
    @inject
    async def handle(
        ctx: Context,
        request_dep: FromDishka[RequestDep],
    ) -> str:
        _ = ctx
        return str(request_dep)

    typed_handle: Callable[[Context], Awaitable[str]] = handle
    context = make_context()

    with pytest.raises(DishkaError, match="Dishka container not found"):
        await typed_handle(context)


@pytest.mark.asyncio()
async def test_inject_request_cleanup_on_exception(
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
async def test_llm_call_request_dependency(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        events = make_llm_events()

        @inject
        async def handle(
            ctx: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

        typed_handle: Callable[[Context], Awaitable[str]] = handle
        instance = middleware(event, context)

        async def call_next(
            evs: Sequence[BaseEvent],
            ctx: Context,
        ) -> ModelResponse:
            result = await typed_handle(ctx)
            return ModelResponse(message=result)

        result = await instance.on_llm_call(call_next, events, context)
        assert result.message == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_human_input_request_dependency(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        human_event = make_human_input_request()

        @inject
        async def handle(
            ctx: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "yes"

        typed_handle: Callable[[Context], Awaitable[str]] = handle
        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: Context,
        ) -> HumanMessage:
            await typed_handle(ctx)
            return HumanMessage(content="yes")

        result = await instance.on_human_input(
            call_next,
            human_event,
            context,
        )
        assert result.content == "yes"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_human_input_provides_event(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        human_event = make_human_input_request("Approve?")

        @inject
        async def handle(
            ctx: Context,
            hi_request: FromDishka[HumanInputRequest],
        ) -> str:
            _ = ctx
            return str(hi_request.content)

        typed_handle: Callable[[Context], Awaitable[str]] = handle
        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: Context,
        ) -> HumanMessage:
            content = await typed_handle(ctx)
            return HumanMessage(content=content)

        result = await instance.on_human_input(
            call_next,
            human_event,
            context,
        )
        assert result.content == "Approve?"
