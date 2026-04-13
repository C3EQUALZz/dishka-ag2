"""Container binding tests for DishkaSyncMiddleware."""

from unittest.mock import Mock

import pytest

from dishka_ag2._consts import CONTAINER_NAME
from tests.common import AppProvider
from tests.conftest import make_context, make_tool_call
from tests.unit.conftest import create_ag2_env


@pytest.mark.asyncio()
async def test_init_preserves_existing_container(
    app_provider: AppProvider,
) -> None:
    async with create_ag2_env(
        app_provider,
        use_async_container=False,
    ) as (root, middleware):
        user_container = Mock()
        context = make_context()
        context.dependencies[CONTAINER_NAME] = user_container
        event = make_tool_call()

        middleware(event, context)

        assert context.dependencies[CONTAINER_NAME] is user_container
        assert context.dependencies[CONTAINER_NAME] is not root
