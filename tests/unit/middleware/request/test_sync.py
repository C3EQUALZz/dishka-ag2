"""REQUEST scope tests for DishkaSyncMiddleware."""

from collections.abc import Sequence
from unittest.mock import Mock

import pytest
from ag2.context import ConversationContext
from ag2.events import (
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
    make_model_response,
    make_tool_call,
    response_content,
    tool_result_content,
)
from tests.unit.conftest import create_ag2_env


@pytest.mark.asyncio()
async def test_request_dependency(app_provider: AppProvider) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        def handle(
            ctx: ConversationContext,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: ConversationContext,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=handle(ctx),
            )

        result = await instance.on_tool_execution(call_next, event, context)
        assert isinstance(result, ToolResultEvent)
        assert tool_result_content(result) == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_injection_uses_positional_context(
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
            context: ConversationContext,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return str(context.variables)

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: ConversationContext,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=handle(ctx),
            )

        result = await instance.on_tool_execution(call_next, event, context)
        assert isinstance(result, ToolResultEvent)
        assert tool_result_content(result) == "{}"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)


@pytest.mark.asyncio()
async def test_request_scope_per_tool_call(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):

        @inject
        def handle(
            ctx: ConversationContext,
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
                ctx: ConversationContext,
            ) -> ToolResultEvent:
                return ToolResultEvent.from_call(
                    ev,
                    result=handle(ctx),
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
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: ConversationContext,
        ) -> ToolResultEvent:
            pending = ctx.dependencies[PENDING_REQUEST_CONTEXT]
            assert pending[ConversationContext] is ctx
            assert pending[ToolCallEvent] is ev
            return ToolResultEvent.from_call(ev, result="ok")

        await instance.on_tool_execution(call_next, event, context)
        assert PENDING_REQUEST_CONTEXT not in context.dependencies


@pytest.mark.asyncio()
async def test_missing_container_raises() -> None:
    @inject
    def handle(
        ctx: ConversationContext,
        request_dep: FromDishka[RequestDep],
    ) -> str:
        _ = ctx
        return str(request_dep)

    context = make_context()

    with pytest.raises(DishkaError, match="Dishka container not found"):
        handle(context)


@pytest.mark.asyncio()
async def test_inject_request_cleanup_on_exception(
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
            ctx: ConversationContext,
            request_dep: FromDishka[RequestDep],
        ) -> None:
            _ = (ctx, request_dep)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            handle(context)

        assert context.dependencies[CONTAINER_NAME] is root
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_llm_call_request_dependency(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        events = make_llm_events()

        @inject
        def handle(
            ctx: ConversationContext,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

        instance = middleware(event, context)

        async def call_next(
            evs: Sequence[BaseEvent],
            ctx: ConversationContext,
        ) -> ModelResponse:
            result = handle(ctx)
            return make_model_response(result)

        result = await instance.on_llm_call(call_next, events, context)
        assert response_content(result) == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)


@pytest.mark.asyncio()
async def test_human_input_request_dependency(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        human_event = make_human_input_request()

        @inject
        def handle(
            ctx: ConversationContext,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "yes"

        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: ConversationContext,
        ) -> HumanMessage:
            handle(ctx)
            return HumanMessage(content="yes")

        result = await instance.on_human_input(
            call_next,
            human_event,
            context,
        )
        assert result.content == "yes"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)


@pytest.mark.asyncio()
async def test_human_input_provides_event(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        human_event = make_human_input_request("Approve?")

        @inject
        def handle(
            ctx: ConversationContext,
            hi_request: FromDishka[HumanInputRequest],
        ) -> str:
            _ = ctx
            return str(hi_request.content)

        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: ConversationContext,
        ) -> HumanMessage:
            content: str = handle(ctx)
            return HumanMessage(content=content)

        result = await instance.on_human_input(
            call_next,
            human_event,
            context,
        )
        assert result.content == "Approve?"
