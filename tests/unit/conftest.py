import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from autogen.beta.middleware import Middleware
from dishka import make_async_container, make_container

from dishka_ag2 import AG2Provider, DishkaMiddleware
from dishka_ag2._consts import CurrentContainer
from tests.common import AppProvider


async def _close_container(
    container: CurrentContainer,
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
        CurrentContainer,
        Middleware,
    ]
]:
    container: CurrentContainer

    if use_async_container:
        container = make_async_container(provider, AG2Provider())
    else:
        container = make_container(provider, AG2Provider())

    middleware = Middleware(DishkaMiddleware, container=container)

    try:
        yield container, middleware
    finally:
        await _close_container(container)
