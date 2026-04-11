"""Tests for Dishka middleware scope lifecycle."""

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
from tests.conftest import (
    make_context,
    make_human_input_request,
    make_llm_events,
    make_tool_call,
)
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
async def test_async_injection_uses_positional_context(
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

        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            return ToolResultEvent.from_call(
                ev,
                result=await handle(ctx),  # type: ignore[no-untyped-call]
            )

        result = await instance.on_tool_execution(
            call_next,
            event,
            context,
        )

        assert result.result.content == "{}"
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


@pytest.mark.asyncio()
async def test_async_session_container_none_raises(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        context.dependencies[SESSION_CONTAINER_NAME] = None
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            raise AssertionError

        with pytest.raises(DishkaError, match="async session container"):
            await instance.on_tool_execution(
                call_next,
                event,
                context,
            )


@pytest.mark.asyncio()
async def test_sync_session_container_none_raises(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (_, middleware):
        context = make_context()
        context.dependencies[SESSION_CONTAINER_NAME] = None
        event = make_tool_call()
        instance = middleware(event, context)

        async def call_next(
            ev: ToolCallEvent,
            ctx: Context,
        ) -> ToolResultEvent:
            raise AssertionError

        with pytest.raises(DishkaError, match="sync session container"):
            await instance.on_tool_execution(
                call_next,
                event,
                context,
            )


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
async def test_sync_session_scope_via_on_turn(
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
            session_dep: FromDishka[SessionDep],
        ) -> str:
            return str(session_dep)

        instance = middleware(event, context)

        async def turn_body(
            ev: BaseEvent,
            ctx: Context,
        ) -> ModelResponse:
            result = handle(___dishka_context=ctx)
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


# --- LLM call scope (on_llm_call) ---


@pytest.mark.asyncio()
async def test_async_llm_call_request_dependency(
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
            result = await handle(___dishka_context=ctx)
            return ModelResponse(message=result)

        result = await instance.on_llm_call(call_next, events, context)
        assert result.message == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_sync_llm_call_request_dependency(
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
            result = handle(___dishka_context=ctx)
            return ModelResponse(message=result)

        result = await instance.on_llm_call(call_next, events, context)
        assert result.message == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_llm_call_container_cleanup(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        events = make_llm_events()

        instance = middleware(event, context)

        async def call_next(
            evs: Sequence[BaseEvent],
            ctx: Context,
        ) -> ModelResponse:
            assert CONTAINER_NAME in ctx.dependencies
            return ModelResponse(message="ok")

        await instance.on_llm_call(call_next, events, context)
        assert CONTAINER_NAME not in context.dependencies


@pytest.mark.asyncio()
async def test_llm_call_uses_session_container(
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
            events = make_llm_events()

            async def llm_call_next(
                evs: Sequence[BaseEvent],
                llm_ctx: Context,
            ) -> ModelResponse:
                await handle(___dishka_context=llm_ctx)
                return ModelResponse(message="ok")

            await instance.on_llm_call(llm_call_next, events, ctx)

            tool_event = make_tool_call()

            async def tool_call_next(
                tool_ev: ToolCallEvent,
                tool_ctx: Context,
            ) -> ToolResultEvent:
                return ToolResultEvent.from_call(
                    tool_ev,
                    result=await handle(___dishka_context=tool_ctx),
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
async def test_async_human_input_request_dependency(
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
            await handle(___dishka_context=ctx)
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
async def test_sync_human_input_request_dependency(
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
            handle(___dishka_context=ctx)
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
async def test_human_input_container_cleanup(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=True,
    ) as (_, middleware):
        context = make_context()
        event = make_tool_call()
        human_event = make_human_input_request()
        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: Context,
        ) -> HumanMessage:
            assert CONTAINER_NAME in ctx.dependencies
            return HumanMessage(content="ok")

        await instance.on_human_input(
            call_next,
            human_event,
            context,
        )
        assert CONTAINER_NAME not in context.dependencies


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
            hi_request: FromDishka[HumanInputRequest],
        ) -> str:
            return str(hi_request.content)

        instance = middleware(event, context)

        async def call_next(
            ev: HumanInputRequest,
            ctx: Context,
        ) -> HumanMessage:
            content: str = await handle(___dishka_context=ctx)  # type: ignore[no-untyped-call]
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
            human_event = make_human_input_request()

            async def human_call_next(
                hi_ev: HumanInputRequest,
                hi_ctx: Context,
            ) -> HumanMessage:
                await handle(___dishka_context=hi_ctx)
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
                    result=await handle(___dishka_context=tool_ctx),
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
