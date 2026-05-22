from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeCommand:
    type: str
    position: tuple[int, int] | None = None

