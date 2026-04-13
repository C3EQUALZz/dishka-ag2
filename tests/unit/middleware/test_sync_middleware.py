"""Scope lifecycle tests for DishkaSyncMiddleware."""

from collections.abc import Sequence
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
from tests.conftest import (
    make_context,
    make_human_input_request,
    make_llm_events,
    make_tool_call,
)
from tests.unit.conftest import create_ag2_env

# --- REQUEST scope (on_tool_execution) ---


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
            ctx: Context,
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
                result=handle(ctx),
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
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        def handle(
            context: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return str(context.variables)

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=handle(ctx),
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
        use_async_container=False,
    ) as (_, middleware):

        @inject
        def handle(
            ctx: Context,
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
    def handle(
        ctx: Context,
        request_dep: FromDishka[RequestDep],
    ) -> str:
        _ = ctx
        return str(request_dep)

    context = make_context()

    with pytest.raises(DishkaError, match="Dishka container not found"):
        handle(context)


# --- APP scope ---


@pytest.mark.asyncio()
async def test_app_dependency(app_provider: AppProvider) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        def handle(
            ctx: Context,
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
                result=handle(ctx),
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
        use_async_container=False,
    ) as (_, middleware):

        @inject
        def handle(
            ctx: Context,
            app_mock: FromDishka[AppMock],
        ) -> str:
            _ = ctx
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
                    result=handle(ctx),
                )

            await instance.on_tool_execution(call_next, event, context)

    assert len(app_mocks) == 2
    assert app_mocks[0] is app_mocks[1]


# --- SESSION scope (on_turn) ---


@pytest.mark.asyncio()
async def test_session_scope_via_on_turn(
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
            ctx: Context,
            session_dep: FromDishka[SessionDep],
        ) -> str:
            _ = ctx
            return str(session_dep)

        instance = middleware(event, context)

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            result = handle(ctx)
            assert result == str(SESSION_DEP_VALUE)
            return ModelResponse(message=result)

        await instance.on_turn(turn_body, event, context)
        app_provider.session_released.assert_called_once()


@pytest.mark.asyncio()
async def test_session_shared_across_tool_calls(
    app_provider: AppProvider,
) -> None:
    session_deps: list[SessionDep] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        def handle(
            ctx: Context,
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
                        result=handle(tool_ctx),
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
async def test_session_container_restored_to_root(
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
        ) -> ModelResponse:
            assert ctx.dependencies[CONTAINER_NAME] is not root
            return ModelResponse(message="ok")

        await instance.on_turn(turn_body, event, context)
        assert context.dependencies[CONTAINER_NAME] is root


# --- LLM call scope (on_llm_call) ---


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
            ctx: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "ok"

        instance = middleware(event, context)

        async def call_next(
            evs: Sequence[BaseEvent],
            ctx: Context,
        ) -> ModelResponse:
            result = handle(ctx)
            return ModelResponse(message=result)

        result = await instance.on_llm_call(call_next, events, context)
        assert result.message == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)


@pytest.mark.asyncio()
async def test_llm_call_uses_session_container(
    app_provider: AppProvider,
) -> None:
    session_deps: list[SessionDep] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        def handle(
            ctx: Context,
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
            events = make_llm_events()

            async def llm_call_next(
                evs: Sequence[BaseEvent],
                llm_ctx: Context,
            ) -> ModelResponse:
                handle(llm_ctx)
                return ModelResponse(message="ok")

            await instance.on_llm_call(llm_call_next, events, ctx)

            tool_event = make_tool_call()

            async def tool_call_next(
                tool_ev: ToolCallEvent,
                tool_ctx: Context,
            ) -> ToolResultEvent:
                return ToolResultEvent.from_call(
                    tool_ev,
                    result=handle(tool_ctx),
                )

            await instance.on_tool_execution(
                tool_call_next,
                tool_event,
                ctx,
            )
            return ModelResponse(message="done")

        await instance.on_turn(turn_body, event, context)

    assert len(session_deps) == 2
    assert session_deps[0] is session_deps[1]
    assert app_provider.session_released.call_count == 1
    assert app_provider.request_released.call_count == 2


# --- Human input scope (on_human_input) ---


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
            ctx: Context,
            request_dep: FromDishka[RequestDep],
            mock: FromDishka[Mock],
        ) -> str:
            mock(request_dep)
            return "yes"

        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: Context,
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
            ctx: Context,
            hi_request: FromDishka[HumanInputRequest],
        ) -> str:
            _ = ctx
            return str(hi_request.content)

        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: Context,
        ) -> HumanMessage:
            content: str = handle(ctx)
            return HumanMessage(content=content)

        result = await instance.on_human_input(
            call_next,
            human_event,
            context,
        )
        assert result.content == "Approve?"


@pytest.mark.asyncio()
async def test_human_input_uses_session_container(
    app_provider: AppProvider,
) -> None:
    session_deps: list[SessionDep] = []

    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()

        @inject
        def handle(
            ctx: Context,
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
            human_event = make_human_input_request()

            async def human_call_next(
                hi_ev: HumanInputRequest,
                hi_ctx: Context,
            ) -> HumanMessage:
                handle(hi_ctx)
                return HumanMessage(content="ok")

            await instance.on_human_input(
                human_call_next,
                human_event,
                ctx,
            )

            tool_event = make_tool_call()

            async def tool_call_next(
                tool_ev: ToolCallEvent,
                tool_ctx: Context,
            ) -> ToolResultEvent:
                return ToolResultEvent.from_call(
                    tool_ev,
                    result=handle(tool_ctx),
                )

            await instance.on_tool_execution(
                tool_call_next,
                tool_event,
                ctx,
            )
            return ModelResponse(message="done")

        await instance.on_turn(turn_body, event, context)

    assert len(session_deps) == 2
    assert session_deps[0] is session_deps[1]
    assert app_provider.session_released.call_count == 1
    assert app_provider.request_released.call_count == 2
