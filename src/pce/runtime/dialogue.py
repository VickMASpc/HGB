from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Subtitle:
    speaker: str
    text: str


class DialogueSystem:
    def __init__(self) -> None:
        self.queue: list[Subtitle] = []
        self.current: Subtitle | None = None

    @property
    def active(self) -> bool:
        return self.current is not None

    def say(self, speaker: str, text: str) -> None:
        self.queue.append(Subtitle(speaker, text))
        if self.current is None:
            self.current = self.queue.pop(0)

    def start_lines(self, speaker: str, lines: list[str]) -> None:
        for line in lines:
            self.queue.append(Subtitle(speaker, line))
        if self.current is None and self.queue:
            self.current = self.queue.pop(0)

    def advance(self) -> None:
        if self.queue:
            self.current = self.queue.pop(0)
        else:
            self.current = None

