from dataclasses import dataclass, field
from typing import Any


@dataclass
class Step:
    n: int
    tool: str
    args: dict[str, Any]
    observation: str
    ok: bool
    error: str | None = None
    tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class AgentState:
    objective: str
    plan: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    report: str = ""
    done: bool = False
    aborted: bool = False
    abort_reason: str | None = None
    tokens_used: int = 0
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    # verificação de citações: URLs no relatório que existem nas evidências coletadas
    citations_total: int = 0
    citations_supported: int = 0
    unsupported_sources: list[str] = field(default_factory=list)

    @property
    def citation_support_rate(self) -> float:
        return self.citations_supported / self.citations_total if self.citations_total else 1.0
