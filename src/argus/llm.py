"""Cliente LLM único do argus: provider, retry, guarda de resposta vazia e custo real.

Antes cada nó criava seu próprio `AsyncOpenAI` e o custo era estimado com um preço
fixo de gpt-4o-mini. Aqui o cliente é único, o preço vem de uma tabela por modelo e
resposta sem `choices` (o proxy às vezes devolve 200 com corpo vazio) é erro, não
resposta em branco.
"""

import json
import re
from dataclasses import dataclass

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from argus.config import get_settings
from argus.logging import get_logger

log = get_logger(__name__)

JSON_BLOCK = re.compile(r"\{.*\}", re.S)

# US$ por 1M de tokens: (entrada, saída). Valores da tabela do provedor.
# Modelo fora da tabela custa 0 no relatório e emite warning — nunca inventar preço.
PRICES: dict[str, tuple[float, float]] = {
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gpt-4o-mini": (0.15, 0.60),
}


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class Completion:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str
    # quando o modelo escolhe uma ferramenta, o conteúdo vem vazio e a decisão
    # chega em `tool_calls`; os dois formatos precisam ser aceitos.
    tool_calls: tuple[dict, ...] = ()

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.model, self.prompt_tokens, self.completion_tokens)


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    prices = PRICES.get(model)
    if prices is None:
        log.warning("llm.unknown_price", model=model)
        return 0.0
    price_in, price_out = prices
    return (prompt_tokens * price_in + completion_tokens * price_out) / 1e6


def _message(resp):
    """O proxy pode devolver 200 com `choices` nulo; isso é erro, não resposta vazia."""
    if not getattr(resp, "choices", None):
        raise LLMError("resposta sem choices")
    return resp.choices[0].message


def _content(resp) -> str:
    return (getattr(_message(resp), "content", None) or "").strip()


def _tool_calls(resp) -> tuple[dict, ...]:
    calls = getattr(_message(resp), "tool_calls", None) or []
    out = []
    for call in calls:
        fn = getattr(call, "function", None)
        if fn is None:
            continue
        out.append({"name": fn.name, "arguments": fn.arguments or "{}"})
    return tuple(out)


def parse_json(text: str) -> dict:
    if not text:
        raise LLMError("resposta vazia do modelo")
    match = JSON_BLOCK.search(text)
    if not match:
        raise LLMError(f"sem JSON na resposta: {text[:200]}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise LLMError(f"JSON inválido: {exc}: {text[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMError(f"JSON não é objeto: {text[:200]}")
    return data


_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        s = get_settings()
        _client = AsyncOpenAI(
            base_url=s.openai_base_url,
            api_key=s.openai_api_key or "local",
            timeout=s.request_timeout_s,
            max_retries=0,  # o retry é nosso, para conseguir contar tentativas
        )
    return _client


def reset_client() -> None:
    global _client
    _client = None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4), reraise=True)
async def chat(
    messages: list[dict],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    tools: list[dict] | None = None,
    max_tokens: int | None = None,
) -> Completion:
    """Uma chamada de chat com retry em erro transitório e resposta vazia."""
    s = get_settings()
    used = model or s.model
    kwargs: dict = {
        "model": used,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or s.max_output_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    if tools:
        kwargs["tools"] = tools
    if s.reasoning_effort:
        # modelos com raciocínio gastam o orçamento de saída pensando; sem isso a
        # resposta chega vazia quando max_tokens é pequeno.
        kwargs["reasoning_effort"] = s.reasoning_effort

    resp = await get_client().chat.completions.create(**kwargs)
    usage = getattr(resp, "usage", None)
    completion = Completion(
        text=_content(resp),
        prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        model=used,
        tool_calls=_tool_calls(resp),
    )
    if not completion.text and not completion.tool_calls:
        raise LLMError("resposta vazia do modelo")
    return completion


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=0.5, max=6), reraise=True)
async def complete_json(prompt: str, *, model: str | None = None) -> tuple[dict, Completion]:
    """JSON estruturado; o retry cobre JSON inválido, não só erro de transporte."""
    s = get_settings()
    completion = await chat(
        [{"role": "user", "content": prompt}], model=model or s.model, json_mode=True
    )
    return parse_json(completion.text), completion
