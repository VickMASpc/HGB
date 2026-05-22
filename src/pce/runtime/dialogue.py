from __future__ import annotations

from dataclasses import dataclass, field

from pce.shared.models import Action


@dataclass(slots=True)
class Subtitle:
    speaker: str
    text: str


@dataclass(slots=True)
class RuntimeChoice:
    text: str
    target: str | None = None
    actions: list[Action] = field(default_factory=list)


class DialogueSystem:
    def __init__(self) -> None:
        self.queue: list[Subtitle] = []
        self.current: Subtitle | None = None
        self.choices: list[RuntimeChoice] = []

    @property
    def active(self) -> bool:
        return self.current is not None

    def say(self, speaker: str, text: str) -> None:
        self.choices = []
        self.queue.append(Subtitle(speaker, text))
        if self.current is None:
            self.current = self.queue.pop(0)

    def start_lines(self, speaker: str, lines: list[str]) -> None:
        self.choices = []
        for line in lines:
            self.queue.append(Subtitle(speaker, line))
        if self.current is None and self.queue:
            self.current = self.queue.pop(0)

    def show_node(self, speaker: str, text: str, choices: list[RuntimeChoice]) -> None:
        self.queue = []
        self.current = Subtitle(speaker, text)
        self.choices = choices

    def choose(self, index: int) -> RuntimeChoice | None:
        if index < 0 or index >= len(self.choices):
            return None
        choice = self.choices[index]
        self.current = None
        self.choices = []
        return choice

    def advance(self) -> None:
        if self.queue:
            self.current = self.queue.pop(0)
        else:
            self.current = None
            self.choices = []

