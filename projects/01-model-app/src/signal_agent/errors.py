"""Typed failures.

The point of this file: callers branch on error *kind*, not on
`except Exception`. Each class below maps to exactly one recovery strategy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from signal_agent.client import Completion


class SignalError(Exception):
    """Base class for everything this application raises on purpose."""


# --- transport / provider failures ---------------------------------------


class ModelError(SignalError):
    """Any failure while talking to the provider."""


class ModelTimeout(ModelError):
    """The provider did not answer inside the timeout."""


class ModelRateLimited(ModelError):
    """429 (or provider quota). Retryable, usually with Retry-After."""

    def __init__(self, message: str, *, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class ModelUnavailable(ModelError):
    """5xx / connection failure. Retryable until the ceiling."""


class ModelAuthError(ModelError):
    """401/403. Never retryable — a retry cannot fix a bad key."""


class ModelBadRequest(ModelError):
    """400/404/422. Our payload is wrong; retrying only wastes money."""


# --- correctness conditions ----------------------------------------------


class ModelTruncated(SignalError):
    """The response hit max_tokens. A partial answer is not an answer.

    Carries the partial completion so callers can log it without losing context.
    """

    def __init__(self, completion: Completion) -> None:
        super().__init__(
            f"response truncated at {completion.usage.output_tokens} output tokens "
            f"(stop_reason={completion.stop_reason!r})"
        )
        self.completion = completion


class BudgetExceeded(SignalError):
    """This run has spent its allowance. Stop before spending more."""
