import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from autogen.beta.middleware import Middleware
from dishka import AsyncContainer, Container, make_async_container, make_container

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    DishkaSyncMiddleware,
)
from tests.common import AppProvider


async def _close_container(
    container: AsyncContainer | Container,
) -> None:
    result = container.close()
    if inspect.isawaitable(result):
        await result


@asynccontextmanager
async def create_ag2_env(
    provider: AppProvider,
    *,
    use_async_container: bool,
) -> AsyncIterator[
    tuple[
        AsyncContainer | Container,
        Middleware,
    ]
]:
    container: AsyncContainer | Container

    if use_async_container:
        container = make_async_container(
            provider,
            AG2Provider(),
            scopes=AG2Scope,
        )
        middleware = Middleware(DishkaAsyncMiddleware, container=container)
    else:
        container = make_container(
            provider,
            AG2Provider(),
            scopes=AG2Scope,
        )
        middleware = Middleware(DishkaSyncMiddleware, container=container)

    try:
        yield container, middleware
    finally:
        await _close_container(container)
