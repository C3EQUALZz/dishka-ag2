"""Shared fixtures for hitl tests."""

import pytest

from tests.integration.hitl.common import BaseHitlProvider


@pytest.fixture()
def hitl_provider() -> BaseHitlProvider:
    return BaseHitlProvider()
