"""Token counting: real (tiktoken) or estimated (char-based fallback)."""

from __future__ import annotations


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken if available, else estimate.

    Uses cl100k_base encoding (Claude / GPT-4 compatible).
    Falls back to len(text) // 4 if tiktoken is not installed.
    """
    try:
        import tiktoken  # type: ignore[import-not-found]

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // 4)
