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

from dishka_ag2 import FromDishka, inject
from dishka_ag2._consts import CONTAINER_NAME
from tests.common import (
    REQUEST_DEP_VALUE,
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
async def test_request_dependency(app_provider: AppProvider) -> None:
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

        result = await instance.on_tool_execution(call_next, event, context)
        assert result.result.content == "ok"
        app_provider.mock.assert_called_with(REQUEST_DEP_VALUE)
        app_provider.request_released.assert_called_once()


@pytest.mark.asyncio()
async def test_request_container_restored_to_root(
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
        ) -> ToolResultEvent:
            assert ctx.dependencies[CONTAINER_NAME] is not root
            return ToolResultEvent.from_call(ev, result="ok")

        await instance.on_tool_execution(call_next, event, context)
        assert context.dependencies[CONTAINER_NAME] is root


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
        def handle(session_dep: FromDishka[SessionDep]) -> str:
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
