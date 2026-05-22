from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1] / "examples" / "mini_adventure"
    target = tmp_path / "mini_adventure"
    shutil.copytree(source, target)
    return target

