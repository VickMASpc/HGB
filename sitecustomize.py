from __future__ import annotations

import sys
from pathlib import Path


def _prefer_repo_src() -> None:
    repo_root = Path(__file__).resolve().parent
    src_path = repo_root / "src"
    if not src_path.is_dir():
        return
    src_text = str(src_path)
    if src_text in sys.path:
        sys.path.remove(src_text)
    sys.path.insert(0, src_text)


_prefer_repo_src()
