"""Guardas de execução: orçamento, detecção de loop, circuit breaker."""

import hashlib
import json
import time
from dataclasses import dataclass, field


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class BudgetGuard:
    max_steps: int = 18
    max_tokens: int = 180_000
    max_seconds: float = 180.0
    max_cost_usd: float = 0.35
    started: float = field(default_factory=time.monotonic)
    steps: int = 0
    tokens: int = 0
    cost_usd: float = 0.0

    def check(self) -> None:
        if self.steps >= self.max_steps:
            raise BudgetExceeded(f"max_steps={self.max_steps}")
        if self.tokens >= self.max_tokens:
            raise BudgetExceeded(f"max_tokens={self.max_tokens}")
        if time.monotonic() - self.started >= self.max_seconds:
            raise BudgetExceeded(f"max_seconds={self.max_seconds}")
        if self.cost_usd >= self.max_cost_usd:
            raise BudgetExceeded(f"max_cost_usd={self.max_cost_usd}")

    def tick(self, tokens: int = 0, cost: float = 0.0) -> None:
        self.steps += 1
        self.tokens += tokens
        self.cost_usd += cost


def signature(tool: str, args: dict) -> str:
    payload = json.dumps({"t": tool, "a": args}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class LoopDetector:
    limit: int = 3
    history: dict[str, int] = field(default_factory=dict)

    def observe(self, tool: str, args: dict) -> bool:
        """True quando a mesma chamada se repete além do limite."""
        sig = signature(tool, args)
        self.history[sig] = self.history.get(sig, 0) + 1
        return self.history[sig] >= self.limit

    def hits(self, tool: str, args: dict) -> int:
        """Quantas vezes esta chamada exata já foi vista."""
        return self.history.get(signature(tool, args), 0)

    def repeated(self) -> list[str]:
        return [s for s, n in self.history.items() if n >= self.limit]


@dataclass
class CircuitBreaker:
    threshold: int = 3
    cooldown_s: float = 120.0
    failures: dict[str, list[float]] = field(default_factory=dict)
    opened_at: dict[str, float] = field(default_factory=dict)

    def is_open(self, tool: str) -> bool:
        opened = self.opened_at.get(tool)
        if opened is None:
            return False
        if time.monotonic() - opened > self.cooldown_s:
            self.opened_at.pop(tool, None)
            self.failures.pop(tool, None)
            return False
        return True

    def record(self, tool: str, ok: bool) -> None:
        if ok:
            self.failures.pop(tool, None)
            return
        now = time.monotonic()
        recent = [t for t in self.failures.get(tool, []) if now - t < self.cooldown_s]
        recent.append(now)
        self.failures[tool] = recent
        if len(recent) >= self.threshold:
            self.opened_at[tool] = now
