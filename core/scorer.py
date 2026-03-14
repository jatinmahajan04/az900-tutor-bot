"""
Readiness score calculator.
Weights each domain by its share of AZ-900 exam questions (from official Skills Measured).
"""

# Official exam weights (approximate % of questions per domain)
DOMAIN_WEIGHTS = {
    "Cloud Concepts": 0.25,
    "Azure Architecture and Services": 0.35,
    "Azure Management and Governance": 0.30,
}
DEFAULT_WEIGHT = 0.10  # fallback for unknown domains


def compute_readiness(stats: list[dict]) -> tuple[int, dict[str, int]]:
    """
    Given a list of {domain, total, correct} dicts, return:
      - overall weighted readiness score (0-100)
      - per-domain percentage breakdown
    """
    breakdown = {}
    for s in stats:
        if s["total"] == 0:
            continue
        pct = int(s["correct"] / s["total"] * 100)
        breakdown[s["domain"]] = pct

    if not breakdown:
        return 0, {}

    # Weighted average across domains we have data for
    total_weight = 0.0
    weighted_sum = 0.0
    for domain, pct in breakdown.items():
        w = DOMAIN_WEIGHTS.get(domain, DEFAULT_WEIGHT)
        weighted_sum += pct * w
        total_weight += w

    # If some domains have no data, give them 0%
    for domain, w in DOMAIN_WEIGHTS.items():
        if domain not in breakdown:
            total_weight += w  # adds weight but 0 score → drags down average

    overall = int(weighted_sum / total_weight) if total_weight > 0 else 0
    return overall, breakdown
