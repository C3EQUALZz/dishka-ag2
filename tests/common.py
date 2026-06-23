import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine, Iterable
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from typing import TYPE_CHECKING, Any, NewType
from unittest.mock import Mock
from uuid import UUID, uuid4

from autogen.beta.context import Stream, SubId
from autogen.beta.events import BaseEvent
from autogen.beta.events.conditions import Condition
from autogen.beta.types import ClassInfo
from dishka import Provider, provide

from dishka_ag2 import AG2Scope
from dishka_ag2._compat import Context

if TYPE_CHECKING:
    # Added to the Stream protocol in ag2 0.13.4; only needed for type
    # checking against the latest version. Older ag2 releases (run in the
    # nox matrix) lack these names, so they must not be imported at runtime.
    from autogen.beta.events import Input, ModelRequest
    from autogen.beta.types import SendableMessage

AppDep = NewType("AppDep", str)
APP_DEP_VALUE = AppDep("APP")

SessionDep = NewType("SessionDep", str)
SESSION_DEP_VALUE = SessionDep("SESSION")

RequestDep = NewType("RequestDep", str)
REQUEST_DEP_VALUE = RequestDep("REQUEST")

AppMock = NewType("AppMock", Mock)


class AppProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.app_released = Mock()
        self.session_released = Mock()
        self.request_released = Mock()
        self.mock = Mock()
        self._app_mock = AppMock(Mock())

    @provide(scope=AG2Scope.APP)
    def app(self) -> Iterable[AppDep]:
        yield APP_DEP_VALUE
        self.app_released()

    @provide(scope=AG2Scope.APP)
    def app_mock(self) -> AppMock:
        return self._app_mock

    @provide(scope=AG2Scope.SESSION)
    def session(self) -> Iterable[SessionDep]:
        yield SESSION_DEP_VALUE
        self.session_released()

    @provide(scope=AG2Scope.REQUEST)
    def request(self) -> Iterable[RequestDep]:
        yield REQUEST_DEP_VALUE
        self.request_released()

    @provide(scope=AG2Scope.REQUEST)
    def get_mock(self) -> Mock:
        return self.mock


class DummyStream(Stream):
    id: UUID = uuid4()
    pending_messages: "list[ModelRequest]" = []  # noqa: RUF012

    def enqueue(
        self,
        *content: "SendableMessage | Input",
    ) -> None:
        raise NotImplementedError

    def spawn_background(
        self,
        coro: Coroutine[Any, Any, None],
    ) -> asyncio.Task[None]:
        raise NotImplementedError

    async def send(
        self,
        event: BaseEvent,
        context: Context,
    ) -> None:
        pass

    def where(
        self,
        condition: ClassInfo | Condition,  # noqa: ARG002
    ) -> "DummyStream":
        return self

    def join(
        self,
        *,
        max_events: int | None = None,
    ) -> AbstractContextManager[AsyncIterator[BaseEvent]]:
        raise NotImplementedError

    def subscribe(  # type: ignore[override]
        self,
        func: Callable[..., Any] | None = None,
        *,
        interrupt: bool = False,
        sync_to_thread: bool = True,
        condition: Condition | None = None,
    ) -> Callable[[Callable[..., Any]], SubId] | SubId:
        raise NotImplementedError

    def unsubscribe(self, sub_id: SubId) -> None:
        pass

    def sub_scope(
        self,
        func: Callable[..., Any],
        *,
        interrupt: bool = False,
        sync_to_thread: bool = True,
        condition: Condition | None = None,
    ) -> AbstractContextManager[None]:
        raise NotImplementedError

    def get(
        self,
        condition: ClassInfo | Condition,
    ) -> AbstractAsyncContextManager[asyncio.Future[BaseEvent]]:
        raise NotImplementedError
