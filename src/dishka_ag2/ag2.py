__all__ = (
    "CONTAINER_NAME",
    "AG2Provider",
    "AG2Scope",
    "ConversationAsyncContainer",
    "ConversationContainer",
    "DishkaAsyncMiddleware",
    "DishkaSyncMiddleware",
    "inject",
)

from autogen.beta.context import Context
from autogen.beta.events import BaseEvent, HumanInputRequest, ToolCallEvent
from dishka import Provider, from_context

from dishka_ag2._consts import CONTAINER_NAME
from dishka_ag2._injectors import inject
from dishka_ag2._middleware import DishkaAsyncMiddleware, DishkaSyncMiddleware
from dishka_ag2._scope import AG2Scope
from dishka_ag2._types import ConversationAsyncContainer, ConversationContainer


class AG2Provider(Provider):
    event = from_context(BaseEvent, scope=AG2Scope.SESSION)
    context = from_context(Context, scope=AG2Scope.SESSION)
    conversation_async_container = from_context(
        ConversationAsyncContainer,
        scope=AG2Scope.REQUEST,
    )
    conversation_container = from_context(
        ConversationContainer,
        scope=AG2Scope.REQUEST,
    )
    tool_call_event = from_context(ToolCallEvent, scope=AG2Scope.REQUEST)
    human_input_request = from_context(HumanInputRequest, scope=AG2Scope.REQUEST)
