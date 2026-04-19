import pytest
from autogen.beta.events import (
    HumanInputRequest,
    ModelRequest,
    ModelResponse,
    ToolCallEvent,
)

from dishka_ag2._compat import Context
from tests.common import AppProvider, DummyStream

try:
    from autogen.beta.events import ModelMessage

    def make_model_response(content: str) -> ModelResponse:
        return ModelResponse(message=ModelMessage(content=content))

    def response_content(response: ModelResponse) -> str:
        return response.message.content  # type: ignore[union-attr]

except ImportError:  # pragma: no cover - ag2 < 0.12

    def make_model_response(content: str) -> ModelResponse:
        return ModelResponse(message=content)  # type: ignore[arg-type]

    def response_content(response: ModelResponse) -> str:
        return response.message  # type: ignore[return-value]


def make_context() -> Context:
    return Context(stream=DummyStream())


def make_tool_call(
    name: str = "test_tool",
    arguments: str = "{}",
) -> ToolCallEvent:
    return ToolCallEvent(name=name, arguments=arguments)


def make_human_input_request(
    content: str = "Please confirm",
) -> HumanInputRequest:
    return HumanInputRequest(content=content)


def make_llm_events() -> list[ModelRequest]:
    if hasattr(ModelRequest, "ensure_request"):
        return [ModelRequest.ensure_request(["Hello"])]
    return [ModelRequest(content="Hello")]  # type: ignore[call-arg]  # ag2 < 0.12


@pytest.fixture()
def app_provider() -> AppProvider:
    return AppProvider()
