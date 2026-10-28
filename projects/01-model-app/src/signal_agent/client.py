"""The only place that talks to the model provider.

Everything later — tracing (stage 6), budget caps (stage 7), model routing —
is added here once, not at a hundred call sites.

Design notes worth defending out loud:

* The SDK's own retries are disabled (`max_retries=0`) because invisible retries
  hide the one thing you need to debug: how many attempts happened, and why.
* Cost comes from the response (`usage.cost`, OpenRouter includes it when asked),
  not from a hardcoded price table that silently goes stale.
* Truncation is a correctness failure, surfaced as a typed error that still
  carries the partial text.
"""

from __future__ import annotations

import random
import time
import uuid
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import openai
from openai import OpenAI

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
from signal_agent.logging import get_logger

log = get_logger("signal.model")

Message = dict[str, str]

# Provider/network statuses worth another attempt. 402 (OpenRouter: out of
# credits) is deliberately absent — retrying it just burns time.
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 529}


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cost_usd: float | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class Completion:
    text: str
    stop_reason: str
    model: str
    request_id: str
    provider_request_id: str | None
    prompt_version: str
    usage: Usage
    latency_ms: int
    attempts: int

    @property
    def truncated(self) -> bool:
        # OpenAI-protocol providers use "length" when max_tokens was hit.
        return self.stop_reason == "length"


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


def _parse_usage(raw: dict[str, Any] | None) -> Usage:
    if not raw:
        return Usage()
    details = raw.get("completion_tokens_details") or {}
    cost = raw.get("cost")
    return Usage(
        input_tokens=int(raw.get("prompt_tokens") or 0),
        output_tokens=int(raw.get("completion_tokens") or 0),
        reasoning_tokens=int(details.get("reasoning_tokens") or 0),
        cost_usd=float(cost) if cost is not None else None,
    )


def _classify(exc: Exception) -> tuple[ModelError, bool]:
    """Map a provider exception to (typed error, retryable)."""
    # Order matters: subclasses first.
    if isinstance(exc, openai.APITimeoutError):
        return ModelTimeout(f"provider timed out: {exc}"), True
    if isinstance(exc, openai.RateLimitError):
        retry_after = _retry_after(exc)
        return ModelRateLimited(f"rate limited: {exc}", retry_after_s=retry_after), True
    if isinstance(exc, openai.AuthenticationError):
        return ModelAuthError(f"authentication failed: {exc}"), False
    if isinstance(exc, openai.PermissionDeniedError):
        return ModelAuthError(f"permission denied: {exc}"), False
    if isinstance(exc, openai.NotFoundError):
        return ModelBadRequest(f"unknown model or route: {exc}"), False
    if isinstance(exc, openai.BadRequestError):
        return ModelBadRequest(f"request rejected: {exc}"), False
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        if status == 402:
            return ModelError("insufficient credits on the provider account"), False
        if status in RETRYABLE_STATUS:
            return ModelUnavailable(f"provider error {status}: {exc}"), True
        return ModelError(f"provider error {status}: {exc}"), False
    if isinstance(exc, openai.APIConnectionError):
        return ModelUnavailable(f"connection failed: {exc}"), True
    return ModelError(f"unexpected provider failure: {exc}"), False


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class CompletionStream:
    """Iterate for text deltas. `.completion` is filled in when the stream ends.

    Why a wrapper: a generator cannot return a value, and you need the final
    usage/stop_reason after streaming to log cost and detect truncation.
    """

    def __init__(self) -> None:
        self.completion: Completion | None = None
        self._iterator: Iterator[str] | None = None

    def __iter__(self) -> Iterator[str]:
        if self._iterator is None:
            raise RuntimeError("stream was not initialised")
        return self._iterator

    def __next__(self) -> str:
        return next(iter(self))

    @property
    def text(self) -> str:
        return self.completion.text if self.completion else ""


class ModelClient:
    def __init__(
        self,
        settings: Settings,
        *,
        sleep: Callable[[float], None] = time.sleep,
        http_client: Any | None = None,
    ) -> None:
        self._s = settings
        self._sleep = sleep
        self._spend_usd = 0.0
        self._client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=settings.base_url,
            timeout=settings.request_timeout_s,
            # We own retries so every attempt is logged and testable.
            max_retries=0,
            default_headers={
                "HTTP-Referer": settings.referer,
                "X-Title": settings.app_title,
            },
            # Tests inject a scripted transport here; production leaves it None.
            http_client=http_client,
        )

    # --- public api -------------------------------------------------------

    @property
    def spent_usd(self) -> float:
        return self._spend_usd

    def complete(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        prompt_version: str = "unknown",
        raise_on_truncation: bool = True,
    ) -> Completion:
        self._check_budget()
        started = time.perf_counter()
        request_id = _new_request_id()
        payload = self._payload(messages, max_tokens=max_tokens, temperature=temperature)

        response, attempts = self._with_retries(
            lambda: self._client.chat.completions.create(**payload),
            request_id=request_id,
            operation="complete",
        )

        raw: dict[str, Any] = response.model_dump()
        choice = (raw.get("choices") or [{}])[0] or {}
        text = (choice.get("message") or {}).get("content") or ""
        completion = Completion(
            text=text,
            stop_reason=choice.get("finish_reason") or "unknown",
            model=raw.get("model") or self._s.model,
            request_id=request_id,
            provider_request_id=raw.get("id"),
            prompt_version=prompt_version,
            usage=_parse_usage(raw.get("usage")),
            latency_ms=int((time.perf_counter() - started) * 1000),
            attempts=attempts,
        )
        self._record(completion, streaming=False)

        if completion.truncated and raise_on_truncation:
            raise ModelTruncated(completion)
        return completion

    def stream(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        prompt_version: str = "unknown",
        raise_on_truncation: bool = True,
    ) -> CompletionStream:
        self._check_budget()
        holder = CompletionStream()
        holder._iterator = self._stream_impl(
            holder,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            prompt_version=prompt_version,
            raise_on_truncation=raise_on_truncation,
        )
        return holder

    # --- internals --------------------------------------------------------

    def _payload(
        self,
        messages: Sequence[Message],
        *,
        max_tokens: int | None,
        temperature: float | None,
    ) -> dict[str, Any]:
        return {
            "model": self._s.model,
            "messages": list(messages),
            "max_tokens": self._s.max_tokens_per_call if max_tokens is None else max_tokens,
            "temperature": self._s.temperature if temperature is None else temperature,
            # OpenRouter extension: ask for cost on the response.
            "extra_body": {"usage": {"include": True}},
        }

    def _stream_impl(
        self,
        holder: CompletionStream,
        messages: Sequence[Message],
        *,
        max_tokens: int | None,
        temperature: float | None,
        prompt_version: str,
        raise_on_truncation: bool,
    ) -> Iterator[str]:
        started = time.perf_counter()
        request_id = _new_request_id()
        payload = self._payload(messages, max_tokens=max_tokens, temperature=temperature)
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

        parts: list[str] = []
        usage = Usage()
        stop_reason = "unknown"
        provider_request_id: str | None = None
        attempts = 0

        while True:
            attempts += 1
            emitted = False
            try:
                with self._client.chat.completions.create(**payload) as raw_stream:
                    for chunk in raw_stream:
                        data: dict[str, Any] = chunk.model_dump()
                        provider_request_id = data.get("id") or provider_request_id
                        if data.get("usage"):
                            usage = _parse_usage(data["usage"])
                        for choice in data.get("choices") or []:
                            if choice.get("finish_reason"):
                                stop_reason = choice["finish_reason"]
                            delta = (choice.get("delta") or {}).get("content")
                            if delta:
                                emitted = True
                                parts.append(delta)
                                yield delta
                break
            except Exception as exc:
                error, retryable = _classify(exc)
                # If the user already saw tokens, a retry would duplicate output.
                # Restarting is only honest before the first token.
                retryable = retryable and not emitted
                if not retryable or attempts > self._s.max_retries:
                    log.error(
                        "model_call_failed",
                        request_id=request_id,
                        operation="stream",
                        attempt=attempts,
                        error=type(error).__name__,
                        detail=str(error)[:300],
                        partial_chars=sum(len(p) for p in parts),
                    )
                    raise error from exc
                delay = self._backoff(attempts, error)
                log.warning(
                    "model_call_retry",
                    request_id=request_id,
                    operation="stream",
                    attempt=attempts,
                    delay_s=round(delay, 3),
                    error=type(error).__name__,
                )
                self._sleep(delay)

        completion = Completion(
            text="".join(parts),
            stop_reason=stop_reason,
            model=self._s.model,
            request_id=request_id,
            provider_request_id=provider_request_id,
            prompt_version=prompt_version,
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
            attempts=attempts,
        )
        holder.completion = completion
        self._record(completion, streaming=True)

        if completion.truncated and raise_on_truncation:
            raise ModelTruncated(completion)

    def _with_retries(
        self,
        call: Callable[[], Any],
        *,
        request_id: str,
        operation: str,
    ) -> tuple[Any, int]:
        for attempt in range(1, self._s.max_retries + 2):  # 1 initial + N retries
            try:
                return call(), attempt
            except Exception as exc:
                error, retryable = _classify(exc)
                if not retryable or attempt > self._s.max_retries:
                    log.error(
                        "model_call_failed",
                        request_id=request_id,
                        operation=operation,
                        attempt=attempt,
                        error=type(error).__name__,
                        detail=str(error)[:300],
                        retryable=retryable,
                    )
                    raise error from exc

                delay = self._backoff(attempt, error)
                log.warning(
                    "model_call_retry",
                    request_id=request_id,
                    operation=operation,
                    attempt=attempt,
                    delay_s=round(delay, 3),
                    error=type(error).__name__,
                )
                self._sleep(delay)

        raise ModelError("retry loop exhausted without an outcome")  # pragma: no cover

    def _backoff(self, attempt: int, error: Exception) -> float:
        retry_after = getattr(error, "retry_after_s", None)
        if retry_after:
            # The server knows better than our formula; cap it so a bad
            # Retry-After cannot park us for an hour.
            return min(float(retry_after), self._s.retry_max_delay_s)
        base = self._s.retry_base_delay_s * (2 ** (attempt - 1))
        jittered = base * (0.5 + random.random())  # jitter: avoid synchronised retries
        # Cap the *result*, not just the base, or jitter can exceed the ceiling.
        return min(jittered, self._s.retry_max_delay_s)

    def _check_budget(self) -> None:
        if self._spend_usd >= self._s.max_cost_usd:
            log.error(
                "budget_exceeded",
                spent_usd=round(self._spend_usd, 6),
                max_cost_usd=self._s.max_cost_usd,
            )
            raise BudgetExceeded(
                f"spent ${self._spend_usd:.4f} of ${self._s.max_cost_usd:.4f} per run"
            )

    def _record(self, completion: Completion, *, streaming: bool) -> None:
        if completion.usage.cost_usd is None:
            log.warning(
                "cost_unknown",
                request_id=completion.request_id,
                hint="provider did not return usage.cost; budget caps cannot be enforced",
            )
        else:
            self._spend_usd += completion.usage.cost_usd

        log.info(
            "model_call",
            request_id=completion.request_id,
            provider_request_id=completion.provider_request_id,
            model=completion.model,
            prompt_version=completion.prompt_version,
            streaming=streaming,
            stop_reason=completion.stop_reason,
            truncated=completion.truncated,
            input_tokens=completion.usage.input_tokens,
            output_tokens=completion.usage.output_tokens,
            reasoning_tokens=completion.usage.reasoning_tokens,
            cost_usd=completion.usage.cost_usd,
            latency_ms=completion.latency_ms,
            attempts=completion.attempts,
            spent_usd=round(self._spend_usd, 6),
        )
