import json
from typing import Any

from argus import llm
from argus.logging import get_logger
from argus.state import AgentState

log = get_logger(__name__)

PROMPT = """Objetivo: {objective}
Plano:
{plan}
Passos já executados:
{history}
Escolha a próxima ação. Se já houver evidência suficiente, retorne tool="__finish__".
Responda só com JSON: {{"tool": "...", "args": {{...}}, "reasoning": "..."}}"""


async def choose(
    state: AgentState, tool_specs: list[dict[str, Any]], loop_hint: bool
) -> tuple[dict, llm.Completion]:
    history = (
        "\n".join(
            f"- {st.n}. {st.tool}({json.dumps(st.args, ensure_ascii=False)[:200]}) -> "
            f"{'ok' if st.ok else 'ERRO'}: {st.observation[:300]}"
            for st in state.steps[-8:]
        )
        or "(nenhum)"
    )
    prompt = PROMPT.format(
        objective=state.objective,
        plan="\n".join(f"{i + 1}. {p}" for i, p in enumerate(state.plan)),
        history=history,
    )
    if loop_hint:
        prompt += (
            "\nATENÇÃO: a última ação se repetiu sem trazer informação nova. "
            "Mude de ferramenta, mude os argumentos ou finalize."
        )
    completion = await llm.chat(
        [{"role": "user", "content": prompt}], json_mode=True, tools=tool_specs
    )
    if completion.tool_calls:  # o modelo preferiu chamar a função diretamente
        call = completion.tool_calls[0]
        decision = {"tool": call["name"], "args": llm.parse_json(call["arguments"])}
    else:
        decision = llm.parse_json(completion.text)
    decision.setdefault("tool", "__finish__")
    decision.setdefault("args", {})
    if not isinstance(decision["args"], dict):
        decision["args"] = {}
    return decision, completion
