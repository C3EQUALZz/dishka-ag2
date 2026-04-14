from collections.abc import Iterable
from typing import NewType
from unittest.mock import Mock

from autogen.beta.annotations import Context
from autogen.beta.events import HumanInputRequest, ToolCallEvent
from autogen.beta.tools import tool
from dishka import Provider, provide

from dishka_ag2 import AG2Scope

AuditLog = NewType("AuditLog", str)


class BaseHitlProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()
        self.audit_released = Mock()

    @provide(scope=AG2Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=AG2Scope.REQUEST)
    def audit(
        self,
        event: HumanInputRequest,
    ) -> Iterable[AuditLog]:
        yield AuditLog(f"asked: {event.content}")
        self.audit_released()


class ConfirmationService:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self.confirmed = False


class HitlProvider(BaseHitlProvider):
    @provide(scope=AG2Scope.REQUEST)
    def confirmation(
        self,
        event: ToolCallEvent,
    ) -> ConfirmationService:
        return ConfirmationService(tool_name=event.name)


@tool  # type: ignore[untyped-decorator]
async def ask_human(context: Context, prompt: str = "Approve?") -> str:
    answer: str = await context.input(prompt)
    return answer
