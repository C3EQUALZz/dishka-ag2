import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, overload

from autogen.beta.context import Context
from dishka.integrations.base import wrap_injection

from dishka_ag2._consts import PENDING_REQUEST_CONTEXT, ParamsP, ReturnT
from dishka_ag2._container import (
    get_async_container_from_context,
    get_sync_container_from_context,
    walk_to_root,
)
from dishka_ag2._context import build_context_getter
from dishka_ag2._scopes import async_request_scope, sync_request_scope


def _request_context_data(context: Context) -> dict[type, Any]:
    pending: dict[type, Any] | None = context.dependencies.get(
        PENDING_REQUEST_CONTEXT,
    )
    return pending if pending is not None else {Context: context}


def inject_async(
    func: Callable[ParamsP, Awaitable[ReturnT]],
) -> Callable[..., Awaitable[ReturnT]]:
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
) -> Callable[..., ReturnT]:
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
    def wrapper(*args: ParamsP.args, **kwargs: ParamsP.kwargs) -> ReturnT:
        context = get_context(args, kwargs)
        root = walk_to_root(get_sync_container_from_context(context))
        with sync_request_scope(
            context,
            root,
            _request_context_data(context),
        ):
            return inner(*args, **kwargs)

    return wrapper


@overload
def inject(
    func: Callable[..., Awaitable[ReturnT]],
) -> Callable[..., Awaitable[ReturnT]]: ...


@overload
def inject(
    func: Callable[..., ReturnT],
) -> Callable[..., ReturnT]: ...


def inject(
    func: Callable[ParamsP, Any],
) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(func):
        return inject_async(func)
    return inject_sync(func)
