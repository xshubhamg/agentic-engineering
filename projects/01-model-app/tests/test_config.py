from __future__ import annotations

import pytest
from pydantic import ValidationError

from signal_agent.config import Settings


def test_missing_api_key_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("SIGNAL_OPENROUTER_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_key_is_not_exposed_by_repr() -> None:
    settings = Settings(_env_file=None, api_key="sk-or-super-secret")

    assert "sk-or-super-secret" not in repr(settings)
    assert settings.api_key.get_secret_value() == "sk-or-super-secret"


def test_defaults_are_the_documented_ones() -> None:
    settings = Settings(_env_file=None, api_key="k")

    assert settings.base_url == "https://openrouter.ai/api/v1"
    assert settings.temperature == 0.0
    assert settings.max_retries == 3
    assert settings.max_cost_usd > 0
