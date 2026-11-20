from argus import llm
from argus.state import AgentState

PROMPT = """Escreva um relatório em Markdown, em português do Brasil, respondendo ao objetivo
usando SÓ as evidências abaixo. Comece direto pela resposta: não repita estas instruções.
Regras: toda afirmação tem link de fonte entre parênteses; se algo ficou sem evidência,
diga explicitamente que não encontrou; termine com a seção "## Fontes" com as URLs usadas.
Objetivo: {objective}
Evidências:
{findings}"""


async def write(state: AgentState) -> tuple[str, llm.Completion]:
    findings = "\n\n".join(state.findings) or "(nenhuma evidência coletada)"
    completion = await llm.chat(
        [{"role": "user", "content": PROMPT.format(objective=state.objective, findings=findings)}],
        temperature=0.2,
    )
    return completion.text, completion
