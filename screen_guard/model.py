from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    id: int
    title: str
    app: str
