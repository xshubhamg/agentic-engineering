"""Contract tests for ModelClient.

No key, no network, no cost: the provider is a scripted transport. The
assertions are about *behaviour under failure*, which is the part you cannot
verify by clicking around in a terminal.
"""

from __future__ import annotations

import copy
import json

import httpx2
import pytest

from signal_agent.client import ModelClient, _parse_usage
from signal_agent.config import Settings
from signal_agent.errors import (
    BudgetExceeded,
    ModelAuthError,
    ModelBadRequest,
    ModelError,
    ModelRateLimited,
    ModelTimeout,
    ModelTruncated,
    ModelUnavailable,
)

from .conftest import Provider, build_client

MESSAGES = [{"role": "user", "content": "What does this company do?"}]

OK_BODY = {
    "id": "gen-abc123",
    "model": "deepseek/deepseek-v4.1-flash",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "It sells widgets."},
            "finish_reason": "stop",
        }
    ],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "cost": 0.0000123,
    },
}


def _sse(*chunks: dict) -> bytes:
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


# --- happy path -----------------------------------------------------------


def test_complete_returns_text_and_usage(client: ModelClient, provider: Provider) -> None:
    provider.reply(200, json_body=OK_BODY)

    completion = client.complete(MESSAGES, prompt_version="answer@deadbeef")

    assert completion.text == "It sells widgets."
    assert completion.stop_reason == "stop"
    assert completion.truncated is False
    assert completion.attempts == 1
    assert completion.provider_request_id == "gen-abc123"
    assert completion.usage.input_tokens == 10
    assert completion.usage.output_tokens == 5
    assert completion.usage.cost_usd == pytest.approx(0.0000123)
    assert provider.calls == 1


def test_request_carries_model_headers_and_usage_flag(
    client: ModelClient, provider: Provider
) -> None:
    provider.reply(200, json_body=OK_BODY)

    client.complete(MESSAGES)

    request = provider.requests[0]
    payload = json.loads(request.content)
    assert payload["model"] == "deepseek/deepseek-v4.1-flash"
    assert payload["temperature"] == 0.0
    assert payload["usage"] == {"include": True}
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    assert request.headers["x-title"] == "Signal"


# --- correctness conditions ----------------------------------------------


def test_truncation_is_an_error_carrying_the_partial_text(
    client: ModelClient, provider: Provider
) -> None:
    body = copy.deepcopy(OK_BODY)
    body["choices"][0]["finish_reason"] = "length"
    body["choices"][0]["message"]["content"] = "The company was founded in"
    provider.reply(200, json_body=body)

    with pytest.raises(ModelTruncated) as caught:
        client.complete(MESSAGES, max_tokens=8)

    assert caught.value.completion.text == "The company was founded in"
    assert caught.value.completion.truncated is True


def test_truncation_can_be_returned_instead_of_raised(
    client: ModelClient, provider: Provider
) -> None:
    body = copy.deepcopy(OK_BODY)
    body["choices"][0]["finish_reason"] = "length"
    provider.reply(200, json_body=body)

    completion = client.complete(MESSAGES, raise_on_truncation=False)

    assert completion.truncated is True


# --- failure and retry behaviour -----------------------------------------


def test_retries_on_429_then_succeeds(
    client: ModelClient, provider: Provider, sleeps: list[float]
) -> None:
    provider.reply(429, json_body={"error": {"message": "slow down"}})
    provider.reply(200, json_body=OK_BODY)

    completion = client.complete(MESSAGES)

    assert completion.text == "It sells widgets."
    assert completion.attempts == 2
    assert provider.calls == 2
    assert len(sleeps) == 1  # backed off exactly once


def test_honours_retry_after_header(
    settings: Settings, provider: Provider, sleeps: list[float]
) -> None:
    provider.reply(429, json_body={}, headers={"retry-after": "3"})
    provider.reply(200, json_body=OK_BODY)
    client = build_client(settings, sleeps, provider)

    client.complete(MESSAGES)

    assert sleeps == [3.0]


def test_does_not_retry_authentication_failure(
    client: ModelClient, provider: Provider, sleeps: list[float]
) -> None:
    provider.reply(401, json_body={"error": {"message": "bad key"}})

    with pytest.raises(ModelAuthError):
        client.complete(MESSAGES)

    assert provider.calls == 1
    assert sleeps == []


def test_gives_up_after_max_retries_on_5xx(
    client: ModelClient, provider: Provider, sleeps: list[float]
) -> None:
    for _ in range(3):
        provider.reply(503, json_body={"error": {"message": "upstream"}})

    with pytest.raises(ModelUnavailable):
        client.complete(MESSAGES)

    assert provider.calls == 3  # 1 initial + max_retries=2
    assert len(sleeps) == 2


def test_timeout_maps_to_model_timeout(client: ModelClient, provider: Provider) -> None:
    for _ in range(3):
        provider.fail(httpx2.ConnectTimeout("too slow"))

    with pytest.raises(ModelTimeout):
        client.complete(MESSAGES)


def test_out_of_credits_is_not_retried(
    client: ModelClient, provider: Provider, sleeps: list[float]
) -> None:
    provider.reply(402, json_body={"error": {"message": "no credits"}})

    with pytest.raises(ModelError, match="credits"):
        client.complete(MESSAGES)

    assert provider.calls == 1
    assert sleeps == []


def test_bad_request_is_not_retried(
    client: ModelClient, provider: Provider, sleeps: list[float]
) -> None:
    provider.reply(400, json_body={"error": {"message": "bad model"}})

    with pytest.raises(ModelBadRequest):
        client.complete(MESSAGES)

    assert provider.calls == 1
    assert sleeps == []


# --- budget ---------------------------------------------------------------


def test_budget_cap_stops_before_the_next_call(
    settings: Settings, provider: Provider, sleeps: list[float]
) -> None:
    settings.max_cost_usd = 0.00001  # lower than the cost of one call
    client = build_client(settings, sleeps, provider)
    provider.reply(200, json_body=OK_BODY)

    client.complete(MESSAGES)
    with pytest.raises(BudgetExceeded):
        client.complete(MESSAGES)

    assert provider.calls == 1
    assert client.spent_usd == pytest.approx(0.0000123)


# --- streaming ------------------------------------------------------------


def test_stream_accumulates_text_and_final_usage(client: ModelClient, provider: Provider) -> None:
    body = _sse(
        {
            "id": "gen-1",
            "model": "deepseek/deepseek-v4.1-flash",
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Hel"}}],
        },
        {
            "id": "gen-1",
            "model": "deepseek/deepseek-v4.1-flash",
            "choices": [{"index": 0, "delta": {"content": "lo"}}],
        },
        {
            "id": "gen-1",
            "model": "deepseek/deepseek-v4.1-flash",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12,
                "cost": 0.000002,
            },
        },
    )
    provider.reply(200, content=body, headers={"content-type": "text/event-stream"})

    stream = client.stream(MESSAGES)
    deltas = list(stream)

    assert deltas == ["Hel", "lo"]
    assert stream.completion is not None
    assert stream.completion.text == "Hello"
    assert stream.completion.stop_reason == "stop"
    assert stream.completion.usage.output_tokens == 2
    assert stream.completion.usage.cost_usd == pytest.approx(0.000002)


def test_unknown_usage_is_reported_as_none() -> None:
    usage = _parse_usage({"prompt_tokens": 3, "completion_tokens": 4})
    assert usage.cost_usd is None
    assert usage.total_tokens == 7
    assert usage.reasoning_tokens == 0


def test_stream_retries_when_failure_happens_before_first_token(
    client: ModelClient, provider: Provider
) -> None:
    provider.fail(httpx2.ConnectTimeout("dropped"))
    provider.reply(
        200,
        content=_sse(
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-v4.1-flash",
                "choices": [{"index": 0, "delta": {"content": "ok"}}],
            },
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-v4.1-flash",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.000001},
            },
        ),
        headers={"content-type": "text/event-stream"},
    )

    stream = client.stream(MESSAGES)

    assert "".join(stream) == "ok"
    assert stream.completion is not None
    assert stream.completion.attempts == 2


def test_stream_truncation_raises_after_delivering_partial_text(
    client: ModelClient, provider: Provider
) -> None:
    provider.reply(
        200,
        content=_sse(
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-v4.1-flash",
                "choices": [{"index": 0, "delta": {"content": "half an ans"}}],
            },
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-v4.1-flash",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 3, "cost": 0.000001},
            },
        ),
        headers={"content-type": "text/event-stream"},
    )

    stream = client.stream(MESSAGES)
    with pytest.raises(ModelTruncated) as caught:
        for _ in stream:
            pass

    assert caught.value.completion.text == "half an ans"
    assert caught.value.completion.truncated is True


# --- backoff arithmetic ---------------------------------------------------


def test_backoff_result_never_exceeds_the_cap(
    client: ModelClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force the largest possible jitter; the cap must still hold.
    monkeypatch.setattr("signal_agent.client.random.random", lambda: 0.9999)

    delay = client._backoff(10, ModelError("boom"))

    assert delay <= client._s.retry_max_delay_s


def test_backoff_respects_but_caps_retry_after(client: ModelClient) -> None:
    assert client._backoff(1, ModelRateLimited("slow", retry_after_s=2)) == 2.0
    assert client._backoff(1, ModelRateLimited("slow", retry_after_s=9999)) == (
        client._s.retry_max_delay_s
    )


# --- known limitation -----------------------------------------------------


def test_abandoning_a_stream_early_skips_accounting(
    client: ModelClient, provider: Provider
) -> None:
    """Known limitation: usage and cost are recorded only when the stream drains.

    A caller that breaks out of iteration (a disconnected HTTP client in stage 7)
    never triggers `_record`, so that spend is invisible. Either drain the stream
    or account for the request before iterating.
    """
    provider.reply(
        200,
        content=_sse(
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-v4.1-flash",
                "choices": [{"index": 0, "delta": {"content": "Hel"}}],
            },
            {
                "id": "gen-1",
                "model": "deepseek/deepseek-v4.1-flash",
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.000001},
            },
        ),
        headers={"content-type": "text/event-stream"},
    )

    stream = client.stream(MESSAGES)
    iterator = iter(stream)
    assert next(iterator) == "Hel"
    iterator.close()

    assert stream.completion is None
    assert client.spent_usd == 0.0
