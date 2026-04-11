import inspect
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar, get_type_hints, overload

from autogen.beta.context import Context
from dishka.integrations.base import wrap_injection

from dishka_autogen._consts import CONTEXT_PARAM
from dishka_autogen._container import (
    get_async_container_from_context,
    get_sync_container_from_context,
)

ReturnT = TypeVar("ReturnT")
ParamsP = ParamSpec("ParamsP")


def _find_context_param(func: Callable[ParamsP, Any]) -> str | None:
    hints = get_type_hints(func)
    return next(
        (name for name, hint in hints.items() if hint is Context),
        None,
    )


def inject_async(
    func: Callable[ParamsP, Awaitable[ReturnT]],
) -> Callable[..., Awaitable[ReturnT]]:
    param_name = _find_context_param(func)
    if param_name:
        additional_params = []
    else:
        additional_params = [CONTEXT_PARAM]
        param_name = CONTEXT_PARAM.name

    return wrap_injection(
        func=func,
        container_getter=lambda _, p: get_async_container_from_context(p[param_name]),
        remove_depends=True,
        is_async=True,
        manage_scope=False,
        additional_params=additional_params,
    )


def inject_sync(func: Callable[ParamsP, ReturnT]) -> Callable[..., ReturnT]:
    param_name = _find_context_param(func)
    if param_name:
        additional_params = []
    else:
        additional_params = [CONTEXT_PARAM]
        param_name = CONTEXT_PARAM.name

    return wrap_injection(
        func=func,
        container_getter=lambda _, p: get_sync_container_from_context(p[param_name]),
        remove_depends=True,
        is_async=False,
        manage_scope=False,
        additional_params=additional_params,
    )


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
