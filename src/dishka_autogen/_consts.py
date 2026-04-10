from inspect import Parameter
from typing import Final

from autogen.beta.annotations import Context

CONTAINER_NAME: Final[str] = "dishka_container"

CONTEXT_PARAM: Final[Parameter] = Parameter(
    name="___dishka_context",
    annotation=Context,
    kind=Parameter.KEYWORD_ONLY,
)
