from __future__ import annotations

from typing import Any, Dict, List, Tuple


def compute_total_cost(quote: Dict[str, Any]) -> float:
    """
    Total cost used by the decision engine.

    Note: This matches the project requirement:
      final_cost = item_price + delivery_fee + taxes - discount
    """

    item_price = float(quote.get("item_price", 0) or 0)
    delivery_fee = float(quote.get("delivery_fee", 0) or 0)
    taxes = float(quote.get("taxes", 0) or 0)
    discount = float(quote.get("discount", 0) or 0)
    return item_price + delivery_fee + taxes - discount


def _safe_max(values: List[float]) -> float:
    return max(values) if values else 0.0


def score_platforms(
    platform_quotes: List[Dict[str, Any]],
    *,
    cost_weight: float = 0.5,
    time_weight: float = 0.3,
    discount_weight: float = 0.2,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], str]:
    """
    Score and pick the best platform based on normalized cost/time/discount.

    Score formula (lower is better):
      score =
        (0.5 * normalized_cost) +
        (0.3 * normalized_time) -
        (0.2 * discount_factor)
    """

    if not platform_quotes:
        raise ValueError("No platform quotes provided.")
    if len(platform_quotes) < 2:
        best = platform_quotes[0].copy()
        best["total_cost"] = compute_total_cost(best)
        best["score"] = 0.0
        return best, [best], f"Only one platform available: {best.get('platform', 'Platform')}."

    # Compute totals first.
    quotes_with_total = []
    for q in platform_quotes:
        qq = q.copy()
        qq["total_cost"] = compute_total_cost(qq)
        quotes_with_total.append(qq)

    costs = [float(q["total_cost"]) for q in quotes_with_total]
    times = [float(q.get("delivery_time", 0) or 0) for q in quotes_with_total]
    discounts = [float(q.get("discount", 0) or 0) for q in quotes_with_total]

    max_cost = _safe_max(costs) or 1.0
    max_time = _safe_max(times) or 1.0
    max_discount = _safe_max(discounts) or 1.0

    # Normalizations chosen to match the scoring interpretation:
    # - higher cost/time => higher normalized values => higher score => worse
    # - higher discount => higher discount_factor => lower score => better
    scored_quotes: List[Dict[str, Any]] = []
    for q in quotes_with_total:
        cost_norm = float(q["total_cost"]) / max_cost
        time_norm = float(q.get("delivery_time", 0) or 0) / max_time
        discount_factor = float(q.get("discount", 0) or 0) / max_discount

        score = (float(cost_weight) * cost_norm) + (float(time_weight) * time_norm) - (float(discount_weight) * discount_factor)
        qq = q.copy()
        qq["score"] = score
        scored_quotes.append(qq)

    best_idx = min(range(len(scored_quotes)), key=lambda i: float(scored_quotes[i]["score"]))
    best = scored_quotes[best_idx]

    # Create a human-readable reason.
    cheapest_idx = min(range(len(scored_quotes)), key=lambda i: float(scored_quotes[i]["total_cost"]))
    fastest_idx = min(range(len(scored_quotes)), key=lambda i: float(scored_quotes[i].get("delivery_time", 0) or 0))
    biggest_discount_idx = max(range(len(scored_quotes)), key=lambda i: float(scored_quotes[i].get("discount", 0) or 0))

    def _platform(i: int) -> str:
        return str(scored_quotes[i].get("platform", f"Platform-{i+1}"))

    parts: List[str] = []
    best_platform = _platform(best_idx)

    if best_idx == cheapest_idx:
        parts.append(f"it has the lowest total cost (INR {int(round(best['total_cost']))}).")
    else:
        parts.append(f"it balances cost and time (total INR {int(round(best['total_cost']))}).")

    if best_idx == fastest_idx:
        parts.append(f"it is also the fastest ({int(round(best.get('delivery_time', 0) or 0))} min).")
    else:
        # Mention relative to fastest to avoid lying.
        fastest_time = int(round(scored_quotes[fastest_idx].get("delivery_time", 0) or 0))
        best_time = int(round(best.get("delivery_time", 0) or 0))
        parts.append(f"delivery time is {best_time} min (fastest is {fastest_time} min).")

    best_discount = int(round(best.get("discount", 0) or 0))
    if best_idx == biggest_discount_idx:
        parts.append(f"it offers the biggest discount (INR {best_discount}).")
    else:
        best_discount_platform = _platform(biggest_discount_idx)
        biggest_discount = int(round(scored_quotes[biggest_discount_idx].get("discount", 0) or 0))
        parts.append(f"discount is INR {best_discount} (biggest is {best_discount_platform} at INR {biggest_discount}).")

    # Include scoring contributions for transparency.
    best_cost_norm = float(best["total_cost"]) / max_cost
    best_time_norm = float(best.get("delivery_time", 0) or 0) / max_time
    best_discount_factor = float(best.get("discount", 0) or 0) / max_discount
    parts.append(
        "decision weights: "
        f"cost_w({cost_weight:.2f})*cost({best_cost_norm:.2f}) + time_w({time_weight:.2f})*time({best_time_norm:.2f}) - discount_w({discount_weight:.2f})*discount({best_discount_factor:.2f})."
    )

    reason = f"Use {best_platform} because " + " ".join(parts)
    return best, scored_quotes, reason

