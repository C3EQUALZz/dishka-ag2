import inspect
from collections.abc import Awaitable, Callable, Coroutine
from functools import wraps
from typing import Any, overload

from ag2.context import ConversationContext
from ag2.utils import (
    _to_async as to_async,  # ruff: ignore[import-private-name] - No public API yet.
)
from dishka import AsyncContainer
from dishka.integrations.base import wrap_injection

from dishka_ag2._consts import CONTAINER_NAME, PENDING_REQUEST_CONTEXT
from dishka_ag2._container import (
    get_async_container_from_context,
    get_sync_container_from_context,
    walk_to_root,
)
from dishka_ag2._container_context import async_request_scope, sync_request_scope
from dishka_ag2._context_getter import build_context_getter
from dishka_ag2._types import ParamsP, ReturnT


def _request_context_data(context: ConversationContext) -> dict[Any, Any]:
    pending: dict[Any, Any] | None = context.dependencies.get(
        PENDING_REQUEST_CONTEXT,
    )
    return pending if pending is not None else {ConversationContext: context}


def inject_async(
    func: Callable[ParamsP, Awaitable[ReturnT]],
) -> Callable[..., Coroutine[Any, Any, ReturnT]]:
    get_context, additional_params = build_context_getter(func)

    inner: Callable[..., Awaitable[ReturnT]] = wrap_injection(
        func=func,
        container_getter=lambda args, kwargs: get_async_container_from_context(
            get_context(args, kwargs),
        ),
        remove_depends=True,
        is_async=True,
        manage_scope=False,
        additional_params=additional_params,
    )

    @wraps(inner)
    async def wrapper(*args: ParamsP.args, **kwargs: ParamsP.kwargs) -> ReturnT:
        context = get_context(args, kwargs)
        root = walk_to_root(get_async_container_from_context(context))
        async with async_request_scope(
            context,
            root,
            _request_context_data(context),
        ):
            return await inner(*args, **kwargs)

    return wrapper


def inject_sync(
    func: Callable[ParamsP, ReturnT],
) -> Callable[..., Coroutine[Any, Any, ReturnT]]:
    get_context, additional_params = build_context_getter(func)

    inner: Callable[..., ReturnT] = wrap_injection(
        func=func,
        container_getter=lambda args, kwargs: get_sync_container_from_context(
            get_context(args, kwargs),
        ),
        remove_depends=True,
        is_async=False,
        manage_scope=False,
        additional_params=additional_params,
    )

    @wraps(inner)
    def sync_wrapper(*args: ParamsP.args, **kwargs: ParamsP.kwargs) -> ReturnT:
        context = get_context(args, kwargs)
        root = walk_to_root(get_sync_container_from_context(context))
        with sync_request_scope(
            context,
            root,
            _request_context_data(context),
        ):
            return inner(*args, **kwargs)

    async_inner: Callable[..., Awaitable[ReturnT]] = inject_async(to_async(func))

    @wraps(inner)
    async def wrapper(*args: ParamsP.args, **kwargs: ParamsP.kwargs) -> ReturnT:
        context = get_context(args, kwargs)
        if isinstance(context.dependencies.get(CONTAINER_NAME), AsyncContainer):
            return await async_inner(*args, **kwargs)
        return sync_wrapper(*args, **kwargs)

    return wrapper


@overload
def inject(
    func: Callable[..., Awaitable[ReturnT]],
) -> Callable[..., Coroutine[Any, Any, ReturnT]]: ...


@overload
def inject(
    func: Callable[..., ReturnT],
) -> Callable[..., Coroutine[Any, Any, ReturnT]]: ...


def inject(
    func: Callable[ParamsP, Any],
) -> Callable[..., Coroutine[Any, Any, Any]]:
    if inspect.iscoroutinefunction(func):
        return inject_async(func)
    return inject_sync(func)
