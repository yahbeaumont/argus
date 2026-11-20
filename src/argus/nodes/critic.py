from argus import llm
from argus.state import AgentState

PROMPT = """Avalie se as evidências coletadas bastam para responder ao objetivo.
Objetivo: {objective}
Evidências: {findings}
Responda só com JSON: {{"sufficient": true|false, "missing": "..."}}"""


async def evaluate(state: AgentState) -> tuple[dict, llm.Completion]:
    data, completion = await llm.complete_json(
        PROMPT.format(
            objective=state.objective,
            findings="\n".join(state.findings[-12:]) or "(nenhuma)",
        )
    )
    verdict = {"sufficient": bool(data.get("sufficient")), "missing": data.get("missing", "")}
    return verdict, completion
