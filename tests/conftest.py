import pytest
from autogen.beta.context import Context
from autogen.beta.events import HumanInputRequest, ModelRequest, ToolCallEvent

from tests.common import AppProvider, DummyStream


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
    return [ModelRequest(content="Hello")]


@pytest.fixture()
def app_provider() -> AppProvider:
    return AppProvider()
