# AG2 integration for Dishka

[![Downloads](https://static.pepy.tech/personalized-badge/dishka-ag2?period=month&units=international_system&left_color=grey&right_color=green&left_text=downloads/month)](https://www.pepy.tech/projects/dishka-ag2)
[![Package version](https://img.shields.io/pypi/v/dishka-ag2?label=PyPI)](https://pypi.org/project/dishka-ag2)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/dishka-ag2.svg)](https://pypi.org/project/dishka-ag2)

Though it is not required, you can use *dishka-ag2* integration. It features:

* *APP*, *SESSION* and *REQUEST* scope management using AG2 middleware
* *AG2Provider* for working with `BaseEvent`, `Context` and `ToolCallEvent` in container
* Automatic injection of dependencies into tool handlers via `@inject` decorator

### Scope mapping

| Dishka Scope     | AG2 Hook            | Description                                |
|------------------|---------------------|--------------------------------------------|
| `Scope.APP`      | --                  | Root container, lives for the app lifetime |
| `Scope.SESSION`  | `on_turn`           | Per-conversation turn, shared across tools |
| `Scope.REQUEST`  | `on_tool_execution` | Per-tool-call, created and closed each time|

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
    DishkaAsyncMiddleware,
    DishkaSyncMiddleware,
    FromDishka,
    inject,
)
from dishka import make_async_container, Provider, Scope, provide
```

2. Create provider. You can use `ToolCallEvent` as a factory parameter on *REQUEST* scope, and `BaseEvent` / `Context` on *SESSION* scope

```python
from autogen.beta.events import ToolCallEvent

class MyProvider(Provider):
    @provide(scope=Scope.APP)
    def app_counter(self) -> AppCounter:
        return AppCounter()

    @provide(scope=Scope.SESSION)
    def conversation_state(self) -> ConversationState:
        return ConversationState()

    @provide(scope=Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)

    @provide(scope=Scope.REQUEST)
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

container = make_async_container(MyProvider(), AG2Provider())

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

## AG2Provider context types

`AG2Provider` registers the following AG2 types as context dependencies, so you can use them as factory parameters:

| Type             | Scope     | Description                           |
|------------------|-----------|---------------------------------------|
| `BaseEvent`      | SESSION   | Initial event that started the turn   |
| `Context`        | SESSION   | AG2 context for the current turn      |
| `ToolCallEvent`  | REQUEST   | Event for the current tool invocation |

## Full example

```python
import asyncio

from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.middleware import Middleware
from autogen.beta.testing import TestConfig
from dishka import Provider, Scope, make_async_container, provide

from dishka_ag2 import AG2Provider, DishkaAsyncMiddleware, FromDishka, inject


class AppCounter:
    def __init__(self) -> None:
        self._value = 0

    def increment(self) -> int:
        self._value += 1
        return self._value


class MyProvider(Provider):
    @provide(scope=Scope.APP)
    def app_counter(self) -> AppCounter:
        return AppCounter()


provider = MyProvider()
container = make_async_container(provider, AG2Provider())

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
