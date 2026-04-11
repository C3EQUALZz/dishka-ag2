__all__ = ("AG2Provider", "DishkaAsyncMiddleware", "DishkaSyncMiddleware", "inject")

from autogen.beta.context import Context
from autogen.beta.events import BaseEvent, HumanInputRequest, ToolCallEvent
from dishka import Provider, Scope, from_context

from dishka_ag2._injectors import inject
from dishka_ag2._middleware import DishkaAsyncMiddleware, DishkaSyncMiddleware


class AG2Provider(Provider):
    initial_event = from_context(BaseEvent, scope=Scope.SESSION)
    context = from_context(Context, scope=Scope.SESSION)
    tool_call = from_context(ToolCallEvent, scope=Scope.REQUEST)
    human_input_request = from_context(
        HumanInputRequest,
        scope=Scope.REQUEST,
    )
