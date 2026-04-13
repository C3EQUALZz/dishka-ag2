import inspect
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast, get_type_hints, overload

from autogen.beta.context import Context
from dishka import AsyncContainer, Container, Scope
from dishka.integrations.base import wrap_injection

from dishka_ag2._consts import CONTEXT_PARAM, PENDING_REQUEST_CONTEXT
from dishka_ag2._container import (
    get_async_container_from_context,
    get_sync_container_from_context,
)
from dishka_ag2._scopes import async_request_scope, sync_request_scope

ReturnT = TypeVar("ReturnT")
ParamsP = ParamSpec("ParamsP")
ContainerT = TypeVar("ContainerT", AsyncContainer, Container)


def _find_context_param(func: Callable[..., Any]) -> str | None:
    hints = get_type_hints(func)
    return next(
        (name for name, hint in hints.items() if hint is Context),
        None,
    )


def _resolve_inject_setup(
    func: Callable[..., Any],
) -> tuple[str, inspect.Signature, list[inspect.Parameter]]:
    found = _find_context_param(func)
    if found is not None:
        return found, inspect.signature(func), []
    return CONTEXT_PARAM.name, inspect.signature(func), [CONTEXT_PARAM]


def _resolve_context(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    param_name: str,
    signature: inspect.Signature,
) -> Context:
    found: Context | None = kwargs.get(param_name)
    if found is not None:
        return found
    bound = signature.bind_partial(*args, **kwargs).arguments
    return cast("Context", bound[param_name])


def _walk_to_root(container: ContainerT) -> ContainerT:
    current = container
    while current.scope != Scope.APP and current.parent_container is not None:
        current = current.parent_container
    return current


def _request_context_data(context: Context) -> dict[type, Any]:
    pending: dict[type, Any] | None = context.dependencies.get(
        PENDING_REQUEST_CONTEXT,
    )
    if pending is not None:
        return pending
    return {Context: context}


def inject_async(
    func: Callable[ParamsP, Awaitable[ReturnT]],
) -> Callable[..., Awaitable[ReturnT]]:
    param_name, signature, additional_params = _resolve_inject_setup(func)

    inner: Callable[..., Awaitable[ReturnT]] = wrap_injection(
        func=func,
        container_getter=lambda args, kwargs: get_async_container_from_context(
            _resolve_context(args, kwargs, param_name, signature),
        ),
        remove_depends=True,
        is_async=True,
        manage_scope=False,
        additional_params=additional_params,
    )

    @wraps(inner)
    async def wrapper(*args: Any, **kwargs: Any) -> ReturnT:
        context = _resolve_context(args, kwargs, param_name, signature)
        root = _walk_to_root(get_async_container_from_context(context))
        async with async_request_scope(
            context,
            root,
            _request_context_data(context),
        ):
            return await inner(*args, **kwargs)

    return wrapper


def inject_sync(func: Callable[ParamsP, ReturnT]) -> Callable[..., ReturnT]:
    param_name, signature, additional_params = _resolve_inject_setup(func)

    inner: Callable[..., ReturnT] = wrap_injection(
        func=func,
        container_getter=lambda args, kwargs: get_sync_container_from_context(
            _resolve_context(args, kwargs, param_name, signature),
        ),
        remove_depends=True,
        is_async=False,
        manage_scope=False,
        additional_params=additional_params,
    )

    @wraps(inner)
    def wrapper(*args: Any, **kwargs: Any) -> ReturnT:
        context = _resolve_context(args, kwargs, param_name, signature)
        root = _walk_to_root(get_sync_container_from_context(context))
        with sync_request_scope(
            context,
            root,
            _request_context_data(context),
        ):
            return inner(*args, **kwargs)

    return wrapper


@overload
def inject(
    func: Callable[ParamsP, Awaitable[ReturnT]],
) -> Callable[..., Awaitable[ReturnT]]: ...


@overload
def inject(func: Callable[ParamsP, ReturnT]) -> Callable[..., ReturnT]: ...


def inject(
    func: Callable[ParamsP, Any],
) -> Callable[..., Any]:
    if inspect.iscoroutinefunction(func):
        return inject_async(func)
    return inject_sync(func)
