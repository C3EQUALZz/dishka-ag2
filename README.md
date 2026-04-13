# AG2 integration for Dishka

[![Downloads](https://static.pepy.tech/personalized-badge/dishka-ag2?period=month&units=international_system&left_color=grey&right_color=green&left_text=downloads/month)](https://www.pepy.tech/projects/dishka-ag2)
[![Package version](https://img.shields.io/pypi/v/dishka-ag2?label=PyPI)](https://pypi.org/project/dishka-ag2)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/dishka-ag2.svg)](https://pypi.org/project/dishka-ag2)

Though it is not required, you can use *dishka-ag2* integration. It features:

* `AG2Scope.APP`, `AG2Scope.CONVERSATION`, `AG2Scope.SESSION` and `AG2Scope.REQUEST` scope management using AG2 beta middleware and `@inject`
* `AG2Provider` for working with `BaseEvent`, `Context`, `ToolCallEvent` and `HumanInputRequest` in container
* `ConversationAsyncContainer` and `ConversationContainer` injection for forwarding an open `AG2Scope.CONVERSATION` to nested `Agent.ask()` calls
* Automatic injection of dependencies via `@inject` in supported AG2 hooks

### Scope mapping

| AG2 scope               | AG2 lifecycle                                                                           | Description                                                                                                        |
|-------------------------|-----------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| `AG2Scope.APP`          | Root container                                                                          | Lives for the application/container lifetime.                                                                      |
| `AG2Scope.CONVERSATION` | Explicit conversation container                                                         | Created by `container(scope=AG2Scope.CONVERSATION)` and can be shared across parent and child `Agent.ask()` calls. |
| `AG2Scope.SESSION`      | `on_turn`                                                                               | Created once per `agent.ask()` turn and shared by all nested tool/LLM/HITL calls in that turn.                     |
| `AG2Scope.REQUEST`      | `on_tool_execution`, `on_llm_call`, `on_human_input`, injected prompt/schema validators | Created for each tool execution, LLM call, HITL request, injected dynamic prompt, or injected response validator.  |

## Supported AG2 Features

| AG2 feature                                     | `AG2Scope.APP` | `AG2Scope.CONVERSATION` | `AG2Scope.SESSION` | `AG2Scope.REQUEST` | Notes                                                                                                                                                    |
|-------------------------------------------------|----------------|-------------------------|--------------------|--------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `@agent.tool`                                   | yes            | yes                     | yes                | yes                | Main supported path for injected tools.                                                                                                                  |
| standalone `@tool` in `Agent(..., tools=[...])` | yes            | yes                     | yes                | yes                | Same lifecycle as `@agent.tool`.                                                                                                                         |
| `Toolkit` / custom `Tool` execution             | yes            | yes                     | yes                | yes                | Works for actual tool functions if the custom tool forwards `middleware` in `register()`.                                                                |
| `on_llm_call` middleware path                   | yes            | yes                     | yes                | yes                | `REQUEST` is opened for every model call.                                                                                                                |
| HITL hooks (`hitl_hook=` / `@agent.hitl_hook`)  | yes            | yes                     | yes                | yes                | `HumanInputRequest` is available in `REQUEST` scope.                                                                                                     |
| `@agent.prompt`                                 | yes            | yes                     | no                 | yes                | Dynamic prompts run before middleware is constructed. Use `dependencies={CONTAINER_NAME: container}` so `@inject` can open `REQUEST` from the container. |
| `response_schema` validators                    | yes            | yes                     | no                 | yes                | Injected validators can use `REQUEST` dependencies during `reply.content()` validation.                                                                  |

See the examples directory for runnable examples:

* `examples/ag2_agent_tool.py` - `@agent.tool` with APP, SESSION and REQUEST.
* `examples/ag2_standalone_tool.py` - standalone `@tool` with `tools=[...]`.
* `examples/ag2_standalone_tool_hitl.py` and `examples/ag2_standalone_tool_hitl_arg.py` - HITL hook injection.
* `examples/ag2_dynamic_prompt.py` - `@agent.prompt` with injected APP/REQUEST dependencies.
* `examples/ag2_response_schema.py` - `response_schema` validators with injected APP/REQUEST dependencies.
* `examples/ag2_subagents.py` - parent and child agents sharing one explicit `AG2Scope.CONVERSATION`.
* `examples/ag2_toolkit.py` - AG2 `Toolkit` with injected tool functions.
* `examples/ag2_custom_toolset.py` - custom AG2 `Tool`/toolset with injected `schemas()` and injected tool functions.

## Installation

Install using `pip`

```sh
pip install dishka-ag2
```

Or with `uv`

```sh
uv add dishka-ag2
```

## How to use

1. Import

```python
from dishka_ag2 import (
    AG2Provider,
    CONTAINER_NAME,
    AG2Scope,
    DishkaAsyncMiddleware,
    DishkaSyncMiddleware,
    FromDishka,
    inject,
)
from dishka import make_async_container, Provider, provide
```

2. Create provider. You can use `ToolCallEvent` or `HumanInputRequest` as factory parameters on `REQUEST` scope for tool/HITL requests, and `BaseEvent` / `Context` on `SESSION` scope.

For `@agent.prompt` and `response_schema` validators, `REQUEST` scope is also supported, but it is opened outside a tool/HITL event. Use request factories that do not require `ToolCallEvent` or `HumanInputRequest` in those paths.

```python
from autogen.beta.events import HumanInputRequest, ToolCallEvent

class MyProvider(Provider):
    @provide(scope=AG2Scope.APP)
    def app_counter(self) -> AppCounter:
        return AppCounter()

    @provide(scope=AG2Scope.SESSION)
    def conversation_state(self) -> ConversationState:
        return ConversationState()

    @provide(scope=AG2Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)

    @provide(scope=AG2Scope.REQUEST)
    def audit_log(self, event: HumanInputRequest) -> AuditLog:
        return AuditLog(f"Human was asked: {event.content}")

    @provide(scope=AG2Scope.REQUEST)
    def greeting_service(
        self,
        conversation: ConversationState,
        request: ToolRequestState,
    ) -> GreetingService:
        return GreetingService(conversation=conversation, request=request)
```

3. Mark those of your tool parameters which are to be injected with `FromDishka[]`

```python
@agent.tool
@inject
async def greet_user(
    name: str,
    greeting: FromDishka[GreetingService],
    counter: FromDishka[AppCounter],
) -> str:
    count = counter.increment()
    result = await greeting.greet(name)
    return result
```

4. Setup dishka integration: create container with `AG2Provider()` and pass it to `DishkaAsyncMiddleware` or `DishkaSyncMiddleware` via `Middleware`

```python
from autogen.beta import Agent
from autogen.beta.middleware import Middleware

container = make_async_container(MyProvider(), AG2Provider(), scopes=AG2Scope)

agent = Agent(
    "assistant",
    prompt="Use tools to greet users.",
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)
```

5. Run the agent and close the container when done

```python
async def main() -> None:
    try:
        reply = await agent.ask("Greet Connor and Sara.")
        print(reply.body)
    finally:
        await container.close()
```

## AG2 integration types

`AG2Provider` registers the following AG2 types as context dependencies, so you can use them as factory parameters. Conversation container handles are supplied by `@inject` from the currently open container chain.

| Type                         | Scope   | Description                                         |
|------------------------------|---------|-----------------------------------------------------|
| `BaseEvent`                  | SESSION | Initial event that started the turn                 |
| `Context`                    | SESSION | AG2 context for the current turn                    |
| `ConversationAsyncContainer` | REQUEST | Async handle for the current CONVERSATION container |
| `ConversationContainer`      | REQUEST | Sync handle for the current CONVERSATION container  |
| `ToolCallEvent`              | REQUEST | Event for the current tool invocation               |
| `HumanInputRequest`          | REQUEST | Event for the current HITL request                  |

## Full example

```python
import asyncio

from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from dishka import Provider, make_async_container, provide

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    FromDishka,
    inject,
)


class AppCounter:
    def __init__(self) -> None:
        self._value = 0

    def increment(self) -> int:
        self._value += 1
        return self._value


class MyProvider(Provider):
    @provide(scope=AG2Scope.APP)
    def app_counter(self) -> AppCounter:
        return AppCounter()


provider = MyProvider()
container = make_async_container(provider, AG2Provider(), scopes=AG2Scope)

agent = Agent(
    "assistant",
    prompt="Use tools to count.",
    config=TestConfig(
        ToolCallEvent(name="count", arguments="{}"),
        ToolCallEvent(name="count", arguments="{}"),
        "Done.",
    ),
    middleware=[
        Middleware(DishkaAsyncMiddleware, container=container),
    ],
)


@agent.tool
@inject
async def count(
    counter: FromDishka[AppCounter],
) -> str:
    value = counter.increment()
    return f"count={value}"


async def main() -> None:
    try:
        reply = await agent.ask("Count twice.")
        print(reply.body)
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
```
