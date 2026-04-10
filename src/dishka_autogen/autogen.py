__all__ = (
    "CONTAINER_NAME",
    "SESSION_CONTAINER_NAME",
    "AG2Provider",
    "DishkaMiddleware",
    "inject",
)

from autogen.beta.context import Context
from autogen.beta.events import ToolCallEvent
from dishka import Provider, Scope, from_context

from dishka_autogen._consts import CONTAINER_NAME, SESSION_CONTAINER_NAME
from dishka_autogen._injectors import inject
from dishka_autogen._middleware import DishkaMiddleware


class AG2Provider(Provider):
    context = from_context(Context, scope=Scope.SESSION)
    tool_call = from_context(ToolCallEvent, scope=Scope.REQUEST)
