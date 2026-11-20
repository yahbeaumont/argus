from argus import llm
from argus.logging import get_logger
from argus.state import AgentState

log = get_logger(__name__)

PROMPT = """Decomponha o objetivo em 3 a 6 passos executáveis,
cada um resolvível por UMA ferramenta.
Ferramentas disponíveis: {tools}
Responda só com JSON: {{"plan": ["passo 1", "..."]}}
Objetivo: {objective}"""


async def plan(state: AgentState, tools: list[str]) -> tuple[list[str], llm.Completion]:
    data, completion = await llm.complete_json(
        PROMPT.format(tools=", ".join(tools), objective=state.objective)
    )
    raw = data.get("plan", [])
    steps = [str(s) for s in raw if str(s).strip()][:6] if isinstance(raw, list) else []
    log.info("plan.created", steps=len(steps))
    return steps, completion
