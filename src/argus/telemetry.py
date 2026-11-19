"""Tracer mínimo: spans com duração, atributos e percentis para o bench."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Span:
    name: str
    started: float = field(default_factory=time.monotonic)
    attributes: dict[str, object] = field(default_factory=dict)

    def end(self) -> int:
        return int((time.monotonic() - self.started) * 1000)


@dataclass
class Tracer:
    spans: list[dict] = field(default_factory=list)

    def record(self, name: str, duration_ms: int, **attrs: object) -> None:
        self.spans.append({"name": name, "ms": duration_ms, **attrs})

    @contextmanager
    def span(self, name: str, **attrs: object) -> Iterator[dict[str, object]]:
        """Abre um span; o que for escrito no dicionário vira atributo no fim."""
        started = time.monotonic()
        box: dict[str, object] = dict(attrs)
        try:
            yield box
        finally:
            self.record(name, int((time.monotonic() - started) * 1000), **box)

    def dump(self) -> list[dict]:
        return self.spans

    def by_name(self) -> dict[str, int]:
        """Duração somada por tipo de span — usado nos gráficos de composição."""
        out: dict[str, int] = {}
        for span in self.spans:
            out[span["name"]] = out.get(span["name"], 0) + int(span["ms"])
        return out


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round((p / 100) * (len(ordered) - 1)))
    return ordered[idx]
