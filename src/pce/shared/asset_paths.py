from __future__ import annotations

import shutil
from pathlib import Path


def normalize_relative_path(path: str) -> str:
    normalized = Path(path)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"Project asset paths must be relative and inside the project: {path}")
    return normalized.as_posix()


def project_path(project_root: Path, relative_path: str) -> Path:
    normalized = normalize_relative_path(relative_path)
    return project_root / normalized


def copy_asset(project_root: Path, source: Path, category: str) -> str:
    if category not in {"backgrounds", "sprites", "ui"}:
        raise ValueError(f"Unsupported asset category: {category}")
    target_dir = project_root / "assets" / category
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    shutil.copy2(source, target)
    return target.relative_to(project_root).as_posix()

