"""Model price estimates for cost reporting.

All prices are US dollars per 1M tokens. These are ESTIMATES captured from
publicly posted Anthropic pricing and they drift over time — treat any dollar
figure agent-xray prints as a rough order-of-magnitude, not a bill.
"""

from typing import Dict, Optional, Tuple

# (input, output, cache_write, cache_read) in $/1M tokens.
MODEL_PRICES: Dict[str, Tuple[float, float, float, float]] = {
    "claude-opus-4-": (15.00, 75.00, 18.75, 1.50),
    "claude-sonnet-4-": (3.00, 15.00, 3.75, 0.30),
    "claude-3-7-sonnet-": (3.00, 15.00, 3.75, 0.30),
    "claude-3-5-sonnet-": (3.00, 15.00, 3.75, 0.30),
    "claude-3-5-haiku-": (0.80, 4.00, 1.00, 0.08),
}


def match_model(model: Optional[str]) -> Optional[str]:
    """Return the price-table prefix matching a model id, or None.

    Longest prefix wins, so "claude-sonnet-4-5-20250929" matches
    "claude-sonnet-4-" rather than a shorter accidental prefix.
    """
    if not model:
        return None
    for prefix in sorted(MODEL_PRICES, key=len, reverse=True):
        if model.startswith(prefix):
            return prefix
    return None


def estimate_cost(
    model: Optional[str], usage: Dict[str, int]
) -> Optional[float]:
    """Estimate USD cost for a usage dict. Returns None if unpriced.

    `usage` keys: input_tokens, output_tokens, cache_creation_input_tokens,
    cache_read_input_tokens. Missing keys count as zero.
    """
    prefix = match_model(model)
    if prefix is None:
        return None
    in_p, out_p, cw_p, cr_p = MODEL_PRICES[prefix]
    total = (
        usage.get("input_tokens", 0) / 1_000_000 * in_p
        + usage.get("output_tokens", 0) / 1_000_000 * out_p
        + usage.get("cache_creation_input_tokens", 0) / 1_000_000 * cw_p
        + usage.get("cache_read_input_tokens", 0) / 1_000_000 * cr_p
    )
    return round(total, 4)
