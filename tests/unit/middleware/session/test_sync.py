"""SESSION scope tests for DishkaSyncMiddleware."""

from collections.abc import Sequence

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

from dishka_ag2 import FromDishka, inject
from dishka_ag2._consts import CONTAINER_NAME, SESSION_CONTAINER_NAME
from tests.common import (
    SESSION_DEP_VALUE,
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
            _ = ctx
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


@pytest.mark.asyncio()
async def test_session_scope_cleanup_on_exception(
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
async def test_base_event_injected_at_session(
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
            _ = ctx
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
            _ = ctx
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
