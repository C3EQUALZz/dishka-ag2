import pytest
from autogen.beta.context import Context
from autogen.beta.events import ToolCallEvent

from tests.common import AppProvider, DummyStream


def make_context() -> Context:
    return Context(stream=DummyStream())


def make_tool_call(name: str = "test_tool") -> ToolCallEvent:
    return ToolCallEvent(name=name)


@pytest.fixture()
def app_provider() -> AppProvider:
    return AppProvider()
