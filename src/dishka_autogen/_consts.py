from inspect import Parameter
from typing import Final, TypeAlias

from autogen.beta.annotations import Context
from dishka import AsyncContainer, Container

CurrentContainer: TypeAlias = AsyncContainer | Container

CONTAINER_NAME: Final[str] = "dishka_container"
SESSION_CONTAINER_NAME: Final[str] = "dishka_session_container"

CONTEXT_PARAM: Final[Parameter] = Parameter(
    name="___dishka_context",
    annotation=Context,
    kind=Parameter.KEYWORD_ONLY,
)
