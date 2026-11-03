from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from ag2.middleware import Middleware
from dishka import Provider, make_async_container, make_container

from dishka_ag2 import (
    AG2Provider,
    AG2Scope,
    DishkaAsyncMiddleware,
    DishkaSyncMiddleware,
)


@asynccontextmanager
async def async_env(
    *providers: Provider,
) -> AsyncGenerator[tuple[Any, Middleware], None]:
    container = make_async_container(*providers, AG2Provider(), scopes=AG2Scope)
    middleware = Middleware(DishkaAsyncMiddleware, container=container)
    try:
        yield container, middleware
    finally:
        await container.close()


@asynccontextmanager
async def sync_env(
    *providers: Provider,
) -> AsyncGenerator[tuple[Any, Middleware], None]:
    container = make_container(*providers, AG2Provider(), scopes=AG2Scope)
    middleware = Middleware(DishkaSyncMiddleware, container=container)
    try:
        yield container, middleware
    finally:
        container.close()
