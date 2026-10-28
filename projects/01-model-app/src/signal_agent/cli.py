"""CLI: the smallest possible surface over ModelClient.

Answer -> stdout. Metadata -> stderr. Exit code says what kind of failure it was,
so a shell script can react without parsing logs.
"""

from __future__ import annotations

import argparse
import sys

from pydantic import ValidationError

from signal_agent.client import ModelClient
from signal_agent.config import Settings
from signal_agent.errors import (
    BudgetExceeded,
    ModelAuthError,
    ModelBadRequest,
    ModelRateLimited,
    ModelTimeout,
    ModelTruncated,
    ModelUnavailable,
)
from signal_agent.logging import configure_logging
from signal_agent.prompts import load_prompt

EXIT_OK = 0
EXIT_TRUNCATED = 2
EXIT_AUTH = 3
EXIT_UNAVAILABLE = 4
EXIT_BUDGET = 5
EXIT_BAD_REQUEST = 6
EXIT_CONFIG = 7


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="signal",
        description="Stage 1: one model call, done properly.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ask = sub.add_parser("ask", help="ask the model a single question")
    ask.add_argument("question", nargs="+", help="the question, in quotes")
    ask.add_argument("--stream", action="store_true", help="stream tokens as they arrive")
    ask.add_argument("--max-tokens", type=int, default=None, help="output token cap")
    ask.add_argument(
        "--no-raise-on-truncation",
        action="store_true",
        help="return the partial answer instead of failing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        settings = Settings()
    except ValidationError as exc:
        missing = sorted({str(err["loc"][0]) for err in exc.errors() if err["type"] == "missing"})
        hint = f"missing env var(s): {', '.join(missing)}" if missing else str(exc)
        print(
            f"config error: {hint}\ncopy .env.example to .env and set OPENROUTER_API_KEY",
            file=sys.stderr,
        )
        return EXIT_CONFIG

    configure_logging(settings.log_level, json_output=settings.log_json)
    client = ModelClient(settings)
    prompt = load_prompt("answer")
    question = " ".join(args.question)
    messages = [
        {"role": "system", "content": prompt.text},
        {"role": "user", "content": question},
    ]
    raise_on_truncation = not args.no_raise_on_truncation

    try:
        if args.stream:
            stream = client.stream(
                messages,
                max_tokens=args.max_tokens,
                prompt_version=prompt.version,
                raise_on_truncation=raise_on_truncation,
            )
            for delta in stream:
                print(delta, end="", flush=True)
            print()
            completion = stream.completion
        else:
            completion = client.complete(
                messages,
                max_tokens=args.max_tokens,
                prompt_version=prompt.version,
                raise_on_truncation=raise_on_truncation,
            )
            print(completion.text)
    except ModelTruncated as exc:
        completion = exc.completion
        if not raise_on_truncation:
            pass
        print(
            f"\ntruncated: hit max_tokens after {completion.usage.output_tokens} output tokens. "
            "Raise --max-tokens or ask a narrower question.",
            file=sys.stderr,
        )
        _print_meta(completion)
        return EXIT_TRUNCATED
    except ModelAuthError as exc:
        print(f"auth error: {exc}\ncheck OPENROUTER_API_KEY", file=sys.stderr)
        return EXIT_AUTH
    except (ModelRateLimited, ModelTimeout, ModelUnavailable) as exc:
        print(f"provider unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    except BudgetExceeded as exc:
        print(f"budget exceeded: {exc}", file=sys.stderr)
        return EXIT_BUDGET
    except ModelBadRequest as exc:
        print(f"bad request: {exc}", file=sys.stderr)
        return EXIT_BAD_REQUEST

    _print_meta(completion)
    return EXIT_OK


def _print_meta(completion) -> None:
    cost = (
        f"${completion.usage.cost_usd:.6f}" if completion.usage.cost_usd is not None else "unknown"
    )
    print(
        f"[{completion.model}] stop={completion.stop_reason} "
        f"tokens={completion.usage.input_tokens}/{completion.usage.output_tokens} "
        f"cost={cost} latency={completion.latency_ms}ms "
        f"attempts={completion.attempts} id={completion.request_id}",
        file=sys.stderr,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
