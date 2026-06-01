from __future__ import annotations

from pathlib import Path

_REPO_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "pce"

__path__ = [str(_REPO_PACKAGE)]
