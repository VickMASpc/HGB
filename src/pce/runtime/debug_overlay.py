from __future__ import annotations


class DebugOverlayState:
    def __init__(self) -> None:
        self.enabled = False

    def toggle(self) -> None:
        self.enabled = not self.enabled

