"""Prompt loader — load prompts from markdown files, compute hash/version."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load a prompt file by name (without extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def prompt_hash(content: str) -> str:
    """SHA-256 hash of prompt content for versioning."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def prompt_version(name: str) -> str:
    """Return hash-based version string for a named prompt."""
    content = load_prompt(name)
    return f"v1-{prompt_hash(content)}"
