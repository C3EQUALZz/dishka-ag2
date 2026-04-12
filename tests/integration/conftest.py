from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from autogen.beta.middleware import Middleware
from dishka import Provider, make_async_container, make_container

from dishka_ag2 import AG2Provider, DishkaAsyncMiddleware, DishkaSyncMiddleware


@asynccontextmanager
async def async_env(
    *providers: Provider,
) -> AsyncIterator[tuple[Any, Middleware]]:
    container = make_async_container(*providers, AG2Provider())
    middleware = Middleware(DishkaAsyncMiddleware, container=container)
    try:
        yield container, middleware
    finally:
        await container.close()


@asynccontextmanager
async def sync_env(
    *providers: Provider,
) -> AsyncIterator[tuple[Any, Middleware]]:
    container = make_container(*providers, AG2Provider())
    middleware = Middleware(DishkaSyncMiddleware, container=container)
    try:
        yield container, middleware
    finally:
        container.close()
