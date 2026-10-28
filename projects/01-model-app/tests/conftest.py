from __future__ import annotations

import json
from typing import Any

import httpx2
import pytest

from signal_agent.client import ModelClient
from signal_agent.config import Settings

BASE_URL = "https://openrouter.ai/api/v1"
ENDPOINT = f"{BASE_URL}/chat/completions"


class Provider:
    """A scripted stand-in for OpenRouter.

    Injected at the transport layer, so everything above it — auth header,
    base URL, timeouts, retry classification — is the real code path.
    """

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self._script: list[httpx2.Response | Exception] = []

    def reply(
        self,
        status: int = 200,
        *,
        json_body: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._script.append(
            httpx2.Response(
                status,
                json=json_body,
                content=content,
                headers=headers,
            )
        )

    def fail(self, exc: Exception) -> None:
        self._script.append(exc)

    @property
    def calls(self) -> int:
        return len(self.requests)

    def last_body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if not self._script:
            raise AssertionError(f"unexpected provider call to {request.url}")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def provider() -> Provider:
    return Provider()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        api_key="test-key",
        model="deepseek/deepseek-v4.1-flash",
        temperature=0.0,
        max_retries=2,
        retry_base_delay_s=0.0,
        retry_max_delay_s=30.0,
        max_cost_usd=1.0,
    )


@pytest.fixture
def sleeps() -> list[float]:
    """Captured backoff delays, so tests never actually wait."""
    return []


def build_client(settings: Settings, sleeps: list[float], provider: Provider) -> ModelClient:
    http = httpx2.Client(transport=httpx2.MockTransport(provider))
    return ModelClient(settings, sleep=sleeps.append, http_client=http)


@pytest.fixture
def client(settings: Settings, sleeps: list[float], provider: Provider) -> ModelClient:
    return build_client(settings, sleeps, provider)
