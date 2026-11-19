from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    llm_provider: Literal["openai", "ollama", "vllm"] = "openai"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    model: str = "gpt-5-mini"
    # modelos de raciocínio gastam o orçamento de saída pensando; "minimal" evita
    # resposta vazia. Vazio = não envia o campo.
    reasoning_effort: Literal["", "minimal", "low", "medium", "high"] = ""
    max_output_tokens: int = 1500
    request_timeout_s: float = 60.0

    # --- orçamento por tarefa ---
    max_steps: int = 18
    max_tokens: int = 180_000
    max_seconds: float = 180.0
    max_cost_usd: float = 0.35

    # --- guardas ---
    guards_enabled: bool = True
    loop_repeat_limit: int = 3
    breaker_threshold: int = 3
    breaker_cooldown_s: float = 120.0

    # --- MCP ---
    mcp_command: str = "python"
    mcp_args: str = "-m argus_tools.server"
    search_provider: Literal["ddg", "tavily"] = "ddg"
    tavily_api_key: str = ""

    @field_validator("max_steps")
    @classmethod
    def _steps_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_steps deve ser >= 1")
        return v

    @field_validator("loop_repeat_limit")
    @classmethod
    def _loop_limit_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("loop_repeat_limit deve ser >= 1")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
