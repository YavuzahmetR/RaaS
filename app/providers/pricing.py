"""Token pricing table and cost computation (USD).

Prices are per 1,000,000 tokens, provider/model specific, kept as plain
constants so they are trivial to update when a vendor changes pricing. The rest
of the system reads cost only through `compute_cost()`, so a price change never
touches business logic.

Sources (verify periodically):
  DeepSeek — https://api-docs.deepseek.com/quick_start/pricing
  Gemini   — https://ai.google.dev/gemini-api/docs/pricing
Values below reflect published list prices as of 2026-07 and are a reasonable
default; override in this table if the vendor page differs.
"""

from __future__ import annotations

# provider -> model -> (input_usd_per_1m, output_usd_per_1m)
PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "deepseek": {
        "deepseek-chat": (0.27, 1.10),
        "deepseek-reasoner": (0.55, 2.19),
    },
    "gemini": {
        "gemini-2.0-flash": (0.10, 0.40),
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-1.5-flash": (0.075, 0.30),
        "gemini-1.5-pro": (1.25, 5.00),
    },
    # Stubs: illustrative only — these providers never make real calls.
    "bedrock": {
        "anthropic.claude-3-5-sonnet": (3.00, 15.00),
    },
    "azure": {
        "gpt-4o": (2.50, 10.00),
    },
}

_MILLION = 1_000_000


def compute_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """USD cost of a single call. Unknown models cost 0.0 and never raise, so a
    missing price entry degrades observability gracefully instead of breaking the
    request path."""
    rates = PRICING.get(provider, {}).get(model)
    if rates is None:
        return 0.0
    in_rate, out_rate = rates
    return round((prompt_tokens * in_rate + completion_tokens * out_rate) / _MILLION, 8)
