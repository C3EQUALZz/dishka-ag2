"""Integration tests using agent.ask() with TestConfig."""

from collections.abc import Iterable
from typing import NewType
from unittest.mock import Mock

import pytest
from autogen.beta import Agent, PromptedSchema, ResponseSchema, response_schema
from autogen.beta.annotations import Context
from autogen.beta.events import (
    BaseEvent,
    HumanInputRequest,
    HumanMessage,
    ToolCallEvent,
)
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from autogen.beta.tools import Toolkit, tool
from dishka import Provider, Scope, make_async_container, provide

from dishka_ag2 import AG2Provider, DishkaAsyncMiddleware, FromDishka, inject
from tests.common import (
    APP_DEP_VALUE,
    REQUEST_DEP_VALUE,
    AppDep,
    AppProvider,
    RequestDep,
)

GreetingResult = NewType("GreetingResult", str)


class GreetingProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()
        self.request_released = Mock()

    @provide(scope=Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=Scope.REQUEST)
    def greeting(
        self,
        event: ToolCallEvent,
    ) -> Iterable[GreetingResult]:
        yield GreetingResult(f"Hello from {event.name}")
        self.request_released()


@pytest.mark.asyncio()
async def test_agent_ask_injects_request_deps() -> None:
    greeting_provider = GreetingProvider()
    container = make_async_container(
        greeting_provider,
        AG2Provider(),
    )

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(
                name="greet",
                arguments='{"name": "Alice"}',
            ),
            "Done.",
        ),
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def greet(
        name: str,
        greeting: FromDishka[GreetingResult],
        mock: FromDishka[Mock],
    ) -> str:
        mock(name, greeting)
        return str(greeting)

    reply = await agent.ask("Greet Alice.")

    greeting_provider.mock.assert_called_once_with(
        "Alice",
        GreetingResult("Hello from greet"),
    )
    greeting_provider.request_released.assert_called_once()
    assert reply.body is not None

    await container.close()


@pytest.mark.asyncio()
async def test_agent_ask_multiple_tool_calls(
    app_provider: AppProvider,
) -> None:
    call_count = 0

    container = make_async_container(AG2Provider(), app_provider)

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="inc", arguments="{}"),
            ToolCallEvent(name="inc", arguments="{}"),
            "All done.",
        ),
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def inc(
        request_dep: FromDishka[RequestDep],
    ) -> str:
        nonlocal call_count
        call_count += 1
        return str(request_dep)

    await agent.ask("Increment twice.")

    assert call_count == 2

    await container.close()


@pytest.mark.asyncio()
async def test_agent_ask_toolkit_injects_request_deps(
    app_provider: AppProvider,
) -> None:
    container = make_async_container(app_provider, AG2Provider())
    toolkit = Toolkit()

    @toolkit.tool  # type: ignore[untyped-decorator]
    @inject
    async def check(
        app_dep: FromDishka[AppDep],
        request_dep: FromDishka[RequestDep],
        mock: FromDishka[Mock],
    ) -> str:
        mock(app_dep, request_dep)
        return "ok"

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="check", arguments="{}"),
            "Done.",
        ),
        tools=[
            toolkit,
        ],
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    await agent.ask("Check toolkit.")

    app_provider.mock.assert_called_once_with(
        APP_DEP_VALUE,
        REQUEST_DEP_VALUE,
    )
    app_provider.request_released.assert_called_once()

    await container.close()


@pytest.mark.asyncio()
async def test_agent_ask_app_and_request_deps(
    app_provider: AppProvider,
) -> None:
    container = make_async_container(app_provider, AG2Provider())

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(
                name="check",
                arguments="{}",
            ),
            "Done.",
        ),
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def check(
        app_dep: FromDishka[AppDep],
        request_dep: FromDishka[RequestDep],
        mock: FromDishka[Mock],
    ) -> str:
        mock(app_dep, request_dep)
        return "ok"

    await agent.ask("Check.")

    app_provider.mock.assert_called_once_with(
        APP_DEP_VALUE,
        REQUEST_DEP_VALUE,
    )
    app_provider.request_released.assert_called_once()
    app_provider.app_released.assert_not_called()

    await container.close()
    app_provider.app_released.assert_called_once()


SessionEventDep = NewType("SessionEventDep", str)


class SessionEventProvider(Provider):
    @provide(scope=Scope.SESSION)
    def session_event(
        self,
        event: BaseEvent,
    ) -> SessionEventDep:
        return SessionEventDep(f"turn:{type(event).__name__}")


@pytest.mark.asyncio()
async def test_agent_ask_session_scope_with_base_event() -> None:
    provider = SessionEventProvider()
    container = make_async_container(provider, AG2Provider())

    results: list[str] = []

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="check", arguments="{}"),
            "Done.",
        ),
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def check(
        session_event: FromDishka[SessionEventDep],
    ) -> str:
        results.append(str(session_event))
        return "ok"

    await agent.ask("Check session.")

    assert len(results) == 1
    assert "turn:" in results[0]

    await container.close()


@pytest.mark.asyncio()
async def test_agent_ask_with_prompted_response_schema_and_tool_injection(
    app_provider: AppProvider,
) -> None:
    container = make_async_container(app_provider, AG2Provider())

    ocean_count = ResponseSchema(
        int,
        name="OceanCount",
        description="Number of oceans on Earth.",
    )
    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="check", arguments="{}"),
            '{"data": 5}',
        ),
        response_schema=PromptedSchema(ocean_count),
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def check(
        app_dep: FromDishka[AppDep],
        request_dep: FromDishka[RequestDep],
        mock: FromDishka[Mock],
    ) -> str:
        mock(app_dep, request_dep)
        return "ok"

    reply = await agent.ask("How many oceans are on Earth?")

    assert await reply.content() == 5
    app_provider.mock.assert_called_once_with(
        APP_DEP_VALUE,
        REQUEST_DEP_VALUE,
    )
    app_provider.request_released.assert_called_once()

    await container.close()


@pytest.mark.asyncio()
async def test_agent_ask_with_callable_prompted_response_schema(
    app_provider: AppProvider,
) -> None:
    container = make_async_container(app_provider, AG2Provider())

    @response_schema  # type: ignore[untyped-decorator]
    def parse_int(content: str) -> int:
        return int(content.strip())

    agent = Agent(
        "assistant",
        config=TestConfig("42"),
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    reply = await agent.ask(
        "Return an integer.",
        response_schema=PromptedSchema(parse_int),
    )

    assert await reply.content() == 42

    await container.close()


LLMCallDep = NewType("LLMCallDep", str)


class LLMCallProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()
        self.request_released = Mock()

    @provide(scope=Scope.REQUEST)
    def llm_call_dep(self) -> Iterable[LLMCallDep]:
        yield LLMCallDep("llm_call_value")
        self.request_released()

    @provide(scope=Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock


@pytest.mark.asyncio()
async def test_agent_ask_llm_call_scope() -> None:
    llm_provider = LLMCallProvider()
    container = make_async_container(llm_provider, AG2Provider())

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="ping", arguments="{}"),
            "Done.",
        ),
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    @agent.tool  # type: ignore[untyped-decorator]
    @inject
    async def ping(
        dep: FromDishka[LLMCallDep],
        mock: FromDishka[Mock],
    ) -> str:
        mock(dep)
        return "pong"

    await agent.ask("Ping.")

    llm_provider.mock.assert_called_once_with(LLMCallDep("llm_call_value"))
    assert llm_provider.request_released.call_count >= 1

    await container.close()


HumanInputDep = NewType("HumanInputDep", str)


class HumanInputProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()
        self.request_released = Mock()

    @provide(scope=Scope.REQUEST)
    def human_input_dep(
        self,
        event: HumanInputRequest,
    ) -> Iterable[HumanInputDep]:
        yield HumanInputDep(f"input:{event.content}")
        self.request_released()

    @provide(scope=Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock


@pytest.mark.asyncio()
async def test_hitl_hook_inject_via_argument() -> None:
    provider = HumanInputProvider()
    container = make_async_container(provider, AG2Provider())

    @inject
    async def my_hitl(
        event: HumanInputRequest,
        dep: FromDishka[HumanInputDep],
        mock: FromDishka[Mock],
    ) -> HumanMessage:
        mock(dep)
        return HumanMessage(content="yes")

    @tool  # type: ignore[untyped-decorator]
    @inject
    async def ask_human(context: Context) -> str:
        result: str = await context.input("Confirm?")
        return result

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="ask_human", arguments="{}"),
            "Done.",
        ),
        tools=[ask_human],
        hitl_hook=my_hitl,
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    await agent.ask("Test.")

    provider.mock.assert_called_once_with(
        HumanInputDep("input:Confirm?"),
    )
    provider.request_released.assert_called()

    await container.close()


@pytest.mark.asyncio()
async def test_hitl_hook_inject_via_decorator() -> None:
    provider = HumanInputProvider()
    container = make_async_container(provider, AG2Provider())

    @tool  # type: ignore[untyped-decorator]
    @inject
    async def ask_human(context: Context) -> str:
        result: str = await context.input("Approve?")
        return result

    agent = Agent(
        "assistant",
        config=TestConfig(
            ToolCallEvent(name="ask_human", arguments="{}"),
            "Done.",
        ),
        tools=[ask_human],
        middleware=[Middleware(DishkaAsyncMiddleware, container=container)],
    )

    @agent.hitl_hook  # type: ignore[untyped-decorator]
    @inject
    async def on_human(
        event: HumanInputRequest,
        dep: FromDishka[HumanInputDep],
        mock: FromDishka[Mock],
    ) -> HumanMessage:
        mock(dep)
        return HumanMessage(content="approved")

    await agent.ask("Test.")

    provider.mock.assert_called_once_with(
        HumanInputDep("input:Approve?"),
    )
    provider.request_released.assert_called()

    await container.close()
