"""Loop do agente com guardas. Máquina de estados explícita, sem LangGraph.

Três guardas atuam em pontos diferentes: BudgetGuard antes de cada passo, LoopDetector
na assinatura da chamada (com abandono quando o agente ignora o aviso) e CircuitBreaker
por ferramenta. Tudo é medido por span para o bench conseguir separar custo de latência.
"""

import time

from argus import citations, llm
from argus.config import Settings, get_settings
from argus.guards import BudgetExceeded, BudgetGuard, CircuitBreaker, LoopDetector
from argus.logging import get_logger
from argus.mcp_client import MCPToolbox, summarize_observation
from argus.nodes import actor, critic, planner, writer
from argus.state import AgentState, Step
from argus.telemetry import Tracer

log = get_logger(__name__)

# Orçamento do braço de controle: os limites continuam existindo, mas largos o
# bastante para não dispararem em 18 passos. Assim o A/B mede o comportamento
# sem guarda, e não a ausência de orçamento.
UNGUARDED = (10_000, 10**9, 10_000.0, 10**6)


def build_guards(s: Settings) -> tuple[BudgetGuard, LoopDetector, CircuitBreaker]:
    if s.guards_enabled:
        return (
            BudgetGuard(s.max_steps, s.max_tokens, s.max_seconds, s.max_cost_usd),
            LoopDetector(s.loop_repeat_limit),
            CircuitBreaker(s.breaker_threshold, s.breaker_cooldown_s),
        )
    steps, tokens, seconds, cost = UNGUARDED
    return (
        BudgetGuard(steps, tokens, seconds, cost),
        LoopDetector(steps),
        CircuitBreaker(steps, 0.0),
    )


def _charge(guard: BudgetGuard, completion: llm.Completion) -> None:
    guard.tick(tokens=completion.tokens, cost=completion.cost_usd)


async def run(objective: str) -> tuple[AgentState, Tracer]:
    s = get_settings()
    state = AgentState(objective=objective)
    tracer = Tracer()
    started = time.monotonic()
    guard, loop, breaker = build_guards(s)

    async with MCPToolbox() as box:
        specs = box.specs()
        tool_names = [sp["function"]["name"] for sp in specs]

        with tracer.span("plan") as span:
            state.plan, completion = await planner.plan(state, tool_names)
            _charge(guard, completion)
            span["steps"] = len(state.plan)

        while not state.done:
            try:
                guard.check()
            except BudgetExceeded as exc:
                state.aborted = True
                state.abort_reason = str(exc)
                log.warning("guard.budget", reason=str(exc))
                break

            hint = bool(loop.repeated())
            with tracer.span("actor") as span:
                decision, completion = await actor.choose(state, specs, hint)
                _charge(guard, completion)
                span["tool"] = decision["tool"]
                span["tokens"] = completion.tokens

            tool, args = decision["tool"], decision["args"]
            if tool == "__finish__":
                state.done = True
                break

            repeated = loop.observe(tool, args)
            if repeated and loop.hits(tool, args) > s.loop_repeat_limit:
                # o agente repetiu a mesma chamada depois do aviso: insistir só gasta
                # orçamento, então o loop é encerrado com o que já foi coletado.
                state.aborted = True
                state.abort_reason = f"loop:{tool}"
                state.steps.append(
                    Step(len(state.steps) + 1, tool, args, "chamada repetida após aviso",
                         False, "loop")
                )
                log.warning("guard.loop", tool=tool, hits=loop.hits(tool, args))
                break

            if breaker.is_open(tool):
                log.warning("breaker.open", tool=tool)
                state.steps.append(
                    Step(len(state.steps) + 1, tool, args,
                         "circuito aberto — ferramenta instável", False, "circuit_open")
                )
                continue

            with tracer.span("tool", tool=tool) as span:
                ok, observation = await box.call(tool, args)
                span["ok"] = ok
                span["chars"] = len(observation)
            breaker.record(tool, ok)

            note = ""
            if repeated:
                note = "\n[nota: chamada repetida, sem informação nova]"
            state.steps.append(
                Step(len(state.steps) + 1, tool, args,
                     summarize_observation(observation) + note, ok,
                     None if ok else observation[:300],
                     tokens=completion.tokens, cost_usd=completion.cost_usd)
            )
            if ok:
                state.findings.append(f"[{tool}] {args}\n{observation}")

            with tracer.span("critic") as span:
                verdict, completion = await critic.evaluate(state)
                _charge(guard, completion)
                span["sufficient"] = verdict["sufficient"]
            if verdict["sufficient"]:
                state.done = True

    with tracer.span("writer") as span:
        state.report, completion = await writer.write(state)
        _charge(guard, completion)
        span["chars"] = len(state.report)

    total, supported, unsupported = citations.verify(state.report, state.findings)
    state.citations_total = total
    state.citations_supported = supported
    state.unsupported_sources = unsupported
    if unsupported:
        log.warning("citations.unsupported", n=len(unsupported), sample=unsupported[:2])

    state.tokens_used = guard.tokens
    state.cost_usd = guard.cost_usd
    state.elapsed_s = time.monotonic() - started
    log.info("run.done", steps=len(state.steps), aborted=state.aborted,
             tokens=state.tokens_used, cost=round(state.cost_usd, 4),
             citations=f"{supported}/{total}")
    return state, tracer
