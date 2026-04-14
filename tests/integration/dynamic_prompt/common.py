from typing import NewType

from autogen.beta.annotations import Context
from dishka import Provider, provide

from dishka_ag2 import AG2Scope

TenantId = NewType("TenantId", str)


class PromptService:
    def build(self, context: Context) -> str:
        return f"vars={context.variables}"


class PromptProvider(Provider):
    @provide(scope=AG2Scope.APP)
    def prompt_service(self) -> PromptService:
        return PromptService()

    @provide(scope=AG2Scope.REQUEST)
    def tenant(self) -> TenantId:
        return TenantId("acme")
