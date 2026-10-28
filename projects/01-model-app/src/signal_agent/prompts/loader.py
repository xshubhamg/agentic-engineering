"""Prompts live in files, with a content hash as the version.

Why: a prompt is source code that changes model behaviour. It needs a diff, a
version, and a version that appears in logs and traces so you can attribute a
regression to a specific edit later (stage 6).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from importlib import resources


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str  # e.g. "answer@3f9c1a2b"
    text: str


def load_prompt(name: str) -> Prompt:
    text = (
        resources.files("signal_agent.prompts").joinpath(f"{name}.md").read_text(encoding="utf-8")
    )
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return Prompt(name=name, version=f"{name}@{digest}", text=text)
