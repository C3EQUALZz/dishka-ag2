from pathlib import Path

import pytest

from tests.integration.skills.common import write_skill


@pytest.fixture()
def skills_dir(tmp_path: Path) -> Path:
    """A skills install directory holding a single ``greeting`` skill."""
    return write_skill(tmp_path / "skills")
