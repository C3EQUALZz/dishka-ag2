import pytest
from ag2.context import ConversationContext
from ag2.events import (
    HumanInputRequest,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolCallEvent,
    ToolResultEvent,
)

from tests.common import AppProvider, DummyStream


def make_model_response(content: str) -> ModelResponse:
    return ModelResponse(message=ModelMessage(content=content))


def response_content(response: ModelResponse) -> str:
    return response.message.content  # type: ignore[union-attr]


def tool_result_content(event: ToolResultEvent) -> str:
    """Extract the textual payload from a ToolResultEvent."""
    tool_result = event.result
    if not tool_result.parts:
        return str(tool_result)
    part = tool_result.parts[0]
    return part.content if hasattr(part, "content") else str(part)  # type: ignore[no-any-return,unused-ignore]


def make_context() -> ConversationContext:
    return ConversationContext(stream=DummyStream())


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
    return [ModelRequest.ensure_request(["Hello"])]


@pytest.fixture()
def app_provider() -> AppProvider:
    return AppProvider()
