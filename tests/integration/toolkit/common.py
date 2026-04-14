from unittest.mock import Mock

from autogen.beta.events import ToolCallEvent
from dishka import Provider, provide

from dishka_ag2 import AG2Scope
from tests.integration.scope_state import SessionState, ToolRequestState


class WeatherService:
    def __init__(
        self,
        session: SessionState,
        request: ToolRequestState,
    ) -> None:
        self.session = session
        self.request = request

    def forecast(self, city: str) -> str:
        return f"{city}:sunny tool={self.request.tool_name}"


class ToolkitProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.mock = Mock()

    @provide(scope=AG2Scope.APP)
    def get_mock(self) -> Mock:
        return self.mock

    @provide(scope=AG2Scope.SESSION)
    def session_state(self) -> SessionState:
        return SessionState()

    @provide(scope=AG2Scope.REQUEST)
    def tool_request_state(self, event: ToolCallEvent) -> ToolRequestState:
        return ToolRequestState(tool_name=event.name)

    @provide(scope=AG2Scope.REQUEST)
    def weather_service(
        self,
        session: SessionState,
        request: ToolRequestState,
    ) -> WeatherService:
        return WeatherService(session=session, request=request)
