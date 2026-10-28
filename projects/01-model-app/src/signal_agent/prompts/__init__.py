"""Prompt templates, packaged so `importlib.resources` can read them."""

from signal_agent.prompts.loader import Prompt, load_prompt

__all__ = ["Prompt", "load_prompt"]
