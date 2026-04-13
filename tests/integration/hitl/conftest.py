"""Shared fixtures for hitl tests."""

from collections.abc import Iterable
from typing import NewType
from unittest.mock import Mock

import pytest
from autogen.beta.annotations import Context
from autogen.beta.events import HumanInputRequest
from autogen.beta.tools import tool
from dishka import Provider, Scope, provide

AuditLog = NewType("AuditLog", str)


class BaseHitlProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()
        self.audit_released = Mock()

    @provide(scope=Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=Scope.REQUEST)
    def audit(
        self,
        event: HumanInputRequest,
    ) -> Iterable[AuditLog]:
        yield AuditLog(f"asked: {event.content}")
        self.audit_released()


@tool  # type: ignore[untyped-decorator]
async def ask_human(context: Context, prompt: str = "Approve?") -> str:
    answer: str = await context.input(prompt)
    return answer


@pytest.fixture()
def hitl_provider() -> BaseHitlProvider:
    return BaseHitlProvider()
