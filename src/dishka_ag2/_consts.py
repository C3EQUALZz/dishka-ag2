from inspect import Parameter
from typing import Final

from autogen.beta.annotations import Context

CONTAINER_NAME: Final[str] = "dishka_container"
SESSION_CONTAINER_NAME: Final[str] = "dishka_session_container"
PENDING_REQUEST_CONTEXT: Final[str] = "_dishka_request_context_data"

CONTEXT_PARAM: Final[Parameter] = Parameter(
    name="___dishka_context",
    annotation=Context,
    kind=Parameter.KEYWORD_ONLY,
)
