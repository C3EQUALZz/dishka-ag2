from typing import NewType, ParamSpec, TypeAlias, TypeVar

from dishka import AsyncContainer, Container

CurrentContainer: TypeAlias = AsyncContainer | Container

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
