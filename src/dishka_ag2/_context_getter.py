import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast, get_type_hints

from dishka_ag2._compat import Context
from dishka_ag2._consts import CONTEXT_PARAM


@dataclass(frozen=True)
class ContextGetter:
    param_name: str
    signature: inspect.Signature

    def __call__(
        self,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Context:
        found: Context | None = kwargs.get(self.param_name)
        if found is not None:
            return found
        bound = self.signature.bind_partial(*args, **kwargs).arguments
        return cast("Context", bound[self.param_name])


def build_context_getter(
    func: Callable[..., Any],
) -> tuple[ContextGetter, list[inspect.Parameter]]:
    signature = inspect.signature(func)
    hints = get_type_hints(func)
    existing = next(
        (name for name, hint in hints.items() if hint is Context),
        None,
    )
    if existing is not None:
        return ContextGetter(existing, signature), []
    return ContextGetter(CONTEXT_PARAM.name, signature), [CONTEXT_PARAM]
