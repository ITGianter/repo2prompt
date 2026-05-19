"""Token counting and cost estimation utilities."""

from __future__ import annotations

from ._optional import require_optional

# Rates per million tokens (USD)
_MODEL_RATES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken. Falls back to cl100k_base for unknown models."""
    require_optional("tiktoken", "Token estimation")
    import tiktoken

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def estimate_cost(token_count: int, model: str) -> float | None:
    """Estimate input cost in USD. Returns None if model rate is unknown."""
    rates = _MODEL_RATES.get(model)
    if not rates:
        return None
    return token_count / 1_000_000 * rates["input"]


def format_token_report(token_count: int, model: str, char_count: int) -> str:
    """Format a human-readable token and cost report."""
    lines = [
        "--- Token & Cost Estimation ---",
        f"Characters: {char_count:,}",
        f"Tokens ({model}): {token_count:,}",
    ]
    cost = estimate_cost(token_count, model)
    if cost is not None:
        lines.append(f"Estimated input cost: ${cost:.4f}")
        lines.append("Note: Cost is approximate; actual billing may vary.")
    else:
        lines.append(f"Cost estimation unavailable for model '{model}'.")
    return "\n".join(lines)
