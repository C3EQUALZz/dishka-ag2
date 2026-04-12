"""AG2 Toolkit with injected tools, sync container."""

import pytest
from autogen.beta import Agent
from autogen.beta.events import ToolCallEvent
from autogen.beta.testing import TestConfig
from autogen.beta.tools import Toolkit

from dishka_ag2 import FromDishka, inject
from tests.common import AppProvider, RequestDep
from tests.integration.conftest import sync_env


@pytest.mark.asyncio()
async def test_toolkit_injects_request_sync(
    app_provider: AppProvider,
) -> None:
    results: list[str] = []
    toolkit = Toolkit()

    @toolkit.tool  # type: ignore[untyped-decorator]
    @inject
    def check(
        request_dep: FromDishka[RequestDep],
    ) -> str:
        results.append(str(request_dep))
        return str(request_dep)

    async with sync_env(app_provider) as (_, middleware):
        agent = Agent(
            "assistant",
            config=TestConfig(
                ToolCallEvent(name="check", arguments="{}"),
                "Done.",
            ),
            tools=[toolkit],
            middleware=[middleware],
        )

        await agent.ask("Check.")

    assert results == ["REQUEST"]
    app_provider.request_released.assert_called_once()
