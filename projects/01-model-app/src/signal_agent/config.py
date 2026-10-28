"""Configuration. One object, loaded once, read nowhere else.

If later stages need a new setting, it goes here — not into an ad-hoc
`os.environ[...]` call buried in a function.
"""

from __future__ import annotations

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SIGNAL_",
        extra="ignore",
        populate_by_name=True,
    )

    # --- provider ---------------------------------------------------------
    # OpenRouter speaks the OpenAI wire protocol, so the OpenAI SDK talks to it
    # unchanged. Only the key and base URL differ.
    api_key: SecretStr = Field(
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "SIGNAL_OPENROUTER_API_KEY"),
        description="OpenRouter API key. Required, never defaulted, never logged.",
    )
    base_url: str = "https://openrouter.ai/api/v1"
    referer: str = "https://github.com/xshubhamg/agentic-engineering"
    app_title: str = "Signal"

    # --- model ------------------------------------------------------------
    # One model everywhere. Consistency beats chasing a better model per task;
    # when you need two tiers (stage 5+), add a second field deliberately.
    model: str = "deepseek/deepseek-v4.1-flash"

    # --- generation -------------------------------------------------------
    temperature: float = 0.0
    max_tokens_per_call: int = 1024

    # --- reliability ------------------------------------------------------
    request_timeout_s: float = 60.0
    max_retries: int = 3
    retry_base_delay_s: float = 0.5
    retry_max_delay_s: float = 8.0

    # --- budget -----------------------------------------------------------
    # Enforced client-side, per client instance (== per run, for now).
    max_cost_usd: float = 0.25

    # --- observability ----------------------------------------------------
    env: str = "dev"
    log_level: str = "INFO"
    log_json: bool = True
