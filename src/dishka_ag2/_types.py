from typing import NewType, ParamSpec, TypeVar

from dishka import AsyncContainer, Container

ConversationAsyncContainer = NewType(
    "ConversationAsyncContainer",
    AsyncContainer,
)
ConversationContainer = NewType(
    "ConversationContainer",
    Container,
)

ReturnT = TypeVar("ReturnT")
ParamsP = ParamSpec("ParamsP")
ContainerT = TypeVar("ContainerT", AsyncContainer, Container)
