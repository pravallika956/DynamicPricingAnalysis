from __future__ import annotations
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import math
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

# Ensure local imports work regardless of Streamlit's current working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from engine.scoring import score_platforms
from engine.weather import WeatherInfo, apply_weather_policy, get_weather
from scraper.zomato_scraper import fetch_quote as fetch_zomato
from scraper.swiggy_scraper import fetch_quote as fetch_swiggy
from scraper.magicpin_scraper import fetch_quote as fetch_magicpin

# Streamlit requires this to be the first Streamlit command in the script.
st.set_page_config(page_title="Smart Food Delivery App Selector (India)", layout="centered")

# Custom UI styling (dark theme + card-like containers).
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #0b1020 0%, #0f1731 100%);
        color: #e8ecf5;
    }
    body {
        background: linear-gradient(180deg, #0b1020 0%, #0f1731 100%);
        color: #e8ecf5;
    }
    /* Make main content area transparent so it inherits the app background. */
    section.main {
        background: rgba(0,0,0,0.00);
    }
    /* Streamlit wrapper background for some versions. */
    .block-container {
        background: rgba(0,0,0,0.00);
    }
    .stSidebar {
        background-color: rgba(15, 23, 49, 0.95);
    }
    .stButton>button {
        background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%);
        color: white;
        border-radius: 10px;
        padding: 0.6rem 1.2rem;
    }
    .metric-card {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def minutes_to_str(minutes: Any) -> str:
    try:
        m = int(round(float(minutes)))
        return f"{m}m"
    except Exception:
        return "N/A"


def rupee(x: Any) -> str:
    try:
        return f"₹{int(round(float(x)))}"
    except Exception:
        return "₹0"
st.title("Smart Food Delivery App Selector (India)")
st.caption("Compares Zomato vs Swiggy using cost, time, and discounts (₹ pricing).")


with st.sidebar:
    st.header("How it works")
    st.write(
        "For each platform we estimate (or scrape) item price, delivery/platform fee, taxes, discounts, and delivery time. "
        "Then we compute a normalized score and pick the lowest score as the recommendation."
    )
    st.write("Note: If scraping is blocked, realistic simulated values are used.")
    show_details = st.checkbox("Show data source (scraped vs simulated)", value=True)
    st.divider()

    st.subheader("Scoring preferences")
    st.caption("Tweak weights to match your priority: cheapest vs fastest vs discounts.")
    cost_priority = st.slider("Cost priority", min_value=0.0, max_value=1.0, value=0.5, step=0.05)
    time_priority = st.slider("Time priority", min_value=0.0, max_value=1.0, value=0.3, step=0.05)
    discount_priority = st.slider("Discount priority", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
    # Normalize to sum to ~1 for stable behavior.
    total = cost_priority + time_priority + discount_priority
    if total <= 0:
        cost_w, time_w, discount_w = 0.5, 0.3, 0.2
    else:
        cost_w = cost_priority / total
        time_w = time_priority / total
        discount_w = discount_priority / total


with st.form("food_selector_form"):
    item_name = st.text_input("Item name", value="Chicken Biryani", max_chars=80)
    restaurant_name = st.text_input("Restaurant name", value="Paradise Biryani", max_chars=80)
    location = st.text_input("Location (city or pincode)", value="Hyderabad", max_chars=80)
    submitted = st.form_submit_button("Get Recommendation")


if submitted:
    platform_quotes: List[Dict[str, Any]] = []

    with st.spinner("Fetching prices, fees, discounts and delivery times..."):
        try:
            platform_quotes.append(fetch_zomato(item_name=item_name, restaurant_name=restaurant_name, location=location))
        except Exception as e:
            platform_quotes.append(
                {
                    "platform": "Zomato",
                    "item_price": 0,
                    "delivery_fee": 0,
                    "taxes": 0,
                    "discount": 0,
                    "delivery_time": 0,
                    "data_source": f"error: {e}",
                }
            )
        try:
            platform_quotes.append(fetch_swiggy(item_name=item_name, restaurant_name=restaurant_name, location=location))
        except Exception as e:
            platform_quotes.append(
                {
                    "platform": "Swiggy",
                    "item_price": 0,
                    "delivery_fee": 0,
                    "taxes": 0,
                    "discount": 0,
                    "delivery_time": 0,
                    "data_source": f"error: {e}",
                }
            )

        try:
            platform_quotes.append(fetch_magicpin(item_name=item_name, restaurant_name=restaurant_name, location=location))
        except Exception as e:
            platform_quotes.append(
                {
                    "platform": "Magicpin",
                    "item_price": 0,
                    "delivery_fee": 0,
                    "taxes": 0,
                    "discount": 0,
                    "delivery_time": 0,
                    "data_source": f"error: {e}",
                }
            )

        # Weather-aware policy (simulated) can adjust delivery-time estimates.
        weather = get_weather(location=location)
        platform_quotes, weather_advice = apply_weather_policy(platform_quotes, weather)

        # Score and pick the best (after weather adjustments).
        best_quote, scored_quotes, reason = score_platforms(
            platform_quotes,
            cost_weight=cost_w,
            time_weight=time_w,
            discount_weight=discount_w,
        )

    # Build "Verdict" tags (for UI friendliness only).
    best_platform = best_quote.get("platform")
    best_total_cost = min(int(round(q.get("total_cost", 0) or 0)) for q in scored_quotes)
    fastest_time = min(int(round(q.get("delivery_time", 0) or 0)) for q in scored_quotes)
    max_discount = max(int(round(q.get("discount", 0) or 0)) for q in scored_quotes)

    df = pd.DataFrame(
        [
            {
                "Platform": q.get("platform"),
                "Total Cost": int(round(q.get("total_cost", 0) or 0)),
                "Time": minutes_to_str(q.get("delivery_time")),
                "Discount": rupee(q.get("discount")),
                "Data Source": q.get("data_source", "N/A"),
                "Score": float(q.get("score", math.inf)),
            }
            for q in scored_quotes
        ]
    )
    df = df.sort_values("Total Cost", ascending=True).reset_index(drop=True)

    def _verdict_for_platform(p: str) -> str:
        if p != best_platform:
            return "—"

        # Find that platform's raw quote to compare factor dominance.
        q = next((x for x in scored_quotes if x.get("platform") == p), {})
        tags: List[str] = []
        if int(round(q.get("total_cost", 0) or 0)) == best_total_cost:
            tags.append("Cheapest")
        if int(round(q.get("delivery_time", 0) or 0)) == fastest_time:
            tags.append("Fastest")
        if int(round(q.get("discount", 0) or 0)) == max_discount:
            tags.append("Biggest Discount")

        tag = ", ".join(tags[:2]) if tags else "Best Overall"
        return f"Best ({tag})"

    df["Verdict"] = df["Platform"].apply(_verdict_for_platform)

    # Highlight the recommended platform.
    def _highlight(row: pd.Series) -> List[str]:
        if row.get("Platform") == best_platform:
            return ["background-color: #C6EFCE"] * len(row)
        return [""] * len(row)

    st.subheader("Comparison")
    df_table = df[["Platform", "Total Cost", "Time", "Discount", "Verdict"]].copy()
    styled = df_table.style.apply(_highlight, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.subheader("Weather Impact")
    # Display weather card + advice. We keep this ASCII-safe since it can be reused in logs.
    if weather.condition == "Rainy":
        st.warning(f"Rainy weather detected for {location}. {weather_advice}")
    elif weather.condition == "Cloudy":
        st.info(f"Cloudy weather detected for {location}. {weather_advice}")
    else:
        st.success(f"Weather is clear for {location}. {weather_advice}")
    st.caption(weather.message + f" (time multiplier: {weather.time_multiplier:.2f}x)")

    # Graph inputs for dashboard tabs.
    chart_df = df.copy()
    chart_df["Total Cost (num)"] = chart_df["Total Cost"].astype(float)
    chart_df["Time (min)"] = chart_df["Platform"].map(
        {q.get("platform"): int(q.get("delivery_time", 0) or 0) for q in scored_quotes}
    )
    # Line chart connects points to form a smooth “curve”.
    line_df = chart_df.set_index("Platform")[["Total Cost (num)", "Time (min)"]]

    # Normalized component breakdown (for transparency).
    costs = [float(q.get("total_cost", 0) or 0) for q in scored_quotes]
    times = [float(q.get("delivery_time", 0) or 0) for q in scored_quotes]
    discounts = [float(q.get("discount", 0) or 0) for q in scored_quotes]
    max_cost = max(costs) if costs else 1.0
    max_time = max(times) if times else 1.0
    max_discount = max(discounts) if discounts else 1.0
    comp_rows = []
    for q in scored_quotes:
        cost_norm = float(q.get("total_cost", 0) or 0) / (max_cost or 1.0)
        time_norm = float(q.get("delivery_time", 0) or 0) / (max_time or 1.0)
        discount_factor = float(q.get("discount", 0) or 0) / (max_discount or 1.0)
        comp_rows.append(
            {
                "Platform": q.get("platform"),
                "Cost component (0.5x)": 0.5 * cost_norm,
                "Time component (0.3x)": 0.3 * time_norm,
                "Discount benefit (-0.2x)": -0.2 * discount_factor,
            }
        )
    comp_df = pd.DataFrame(comp_rows).set_index("Platform")

    tabs = st.tabs(["Recommendation", "Dashboards", "Insights"])

    with tabs[0]:
        st.subheader("Recommendation")
        st.write(reason)

        st.subheader("Price Breakdown (Recommended)")
        best_item_price = best_quote.get("item_price", 0) or 0
        best_delivery_fee = best_quote.get("delivery_fee", 0) or 0
        best_taxes = best_quote.get("taxes", 0) or 0
        best_discount = best_quote.get("discount", 0) or 0
        best_total = best_quote.get("total_cost", 0) or 0
        best_time = best_quote.get("delivery_time", 0) or 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Item price", rupee(best_item_price))
        with col2:
            st.metric("Delivery fee + taxes", rupee(best_delivery_fee + best_taxes))
        with col3:
            st.metric("Discount", "-" + rupee(best_discount))

        st.write(f"**Delivery time:** {minutes_to_str(best_time)}")
        st.write(f"**Total cost:** {rupee(best_total)}")

        if show_details:
            with st.expander("Raw details (scraped/simulated inputs)"):
                # Show per-platform breakdown so users can audit the recommendation.
                for q in scored_quotes:
                    st.write(
                        {
                            "platform": q.get("platform"),
                            "item_price": rupee(q.get("item_price", 0) or 0),
                            "delivery_fee": rupee(q.get("delivery_fee", 0) or 0),
                            "taxes": rupee(q.get("taxes", 0) or 0),
                            "discount": rupee(q.get("discount", 0) or 0),
                            "delivery_time": f"{int(q.get('delivery_time', 0) or 0)} min",
                            "data_source": q.get("data_source", "N/A"),
                            "weather_condition": q.get("weather_condition", weather.condition),
                        }
                    )

    with tabs[1]:
        # Dashboards
        st.subheader("Charts (Platform Comparison)")
        # Reuse previous charts but place them inside the dashboard tab.
        st.line_chart(line_df)

        st.subheader("Score component breakdown")
        st.bar_chart(comp_df)

        st.subheader("Uncertainty distribution (simulated)")
        st.write("How the winner might change if item prices/discounts fluctuate slightly.")

        # Run a small simulation to estimate stability of the recommendation.
        import random as _random

        def _sample_quote(q: Dict[str, Any], seed: int, scale: float = 1.0) -> Dict[str, Any]:
            rng = _random.Random(seed)
            qq = q.copy()
            item_price = float(qq.get("item_price", 0) or 0)
            delivery_fee = float(qq.get("delivery_fee", 0) or 0)
            taxes = float(qq.get("taxes", 0) or 0)
            discount = float(qq.get("discount", 0) or 0)
            delivery_time = float(qq.get("delivery_time", 0) or 0)

            # Small integer fluctuations around scraped/simulated values.
            qq["item_price"] = max(0, int(round(item_price * (1 + rng.uniform(-0.08, 0.08) * scale))))
            qq["delivery_fee"] = max(0, int(round(delivery_fee * (1 + rng.uniform(-0.12, 0.12) * scale))))
            qq["taxes"] = max(0, int(round(taxes * (1 + rng.uniform(-0.08, 0.08) * scale))))
            qq["discount"] = max(0, int(round(discount * (1 + rng.uniform(-0.25, 0.25) * scale))))
            qq["delivery_time"] = max(0, int(round(delivery_time * (1 + rng.uniform(-0.18, 0.18) * scale))))
            return qq

        N = 25
        platforms = sorted({str(q.get("platform", "")) for q in platform_quotes if str(q.get("platform", ""))})
        win_counts: Dict[str, int] = {p: 0 for p in platforms}
        totals_by_platform: Dict[str, List[int]] = {p: [] for p in platforms}

        base_seed = abs(hash(f"{item_name}|{restaurant_name}|{location}")) % (2**32)
        for i in range(N):
            sampled = []
            for idx, q in enumerate(platform_quotes):
                sampled.append(_sample_quote(q, seed=base_seed + i * 101 + idx * 17, scale=1.0))
            sampled, _ = apply_weather_policy(sampled, weather)
            best_i, scored_i, _ = score_platforms(
                sampled,
                cost_weight=cost_w,
                time_weight=time_w,
                discount_weight=discount_w,
            )
            winner = str(best_i.get("platform", ""))
            if winner in win_counts:
                win_counts[winner] += 1

            for q in scored_i:
                p = str(q.get("platform", ""))
                if p in totals_by_platform:
                    totals_by_platform[p].append(int(round(q.get("total_cost", 0) or 0)))

        st.write(
            {
                "Simulations": N,
                **{f"{p} wins": c for p, c in win_counts.items()},
            }
        )

        # Histogram-like chart for total cost.
        all_costs: List[int] = []
        for p in platforms:
            all_costs += totals_by_platform.get(p, [])
        if all_costs:
            min_c = min(all_costs)
            max_c = max(all_costs)
            bins = 6
            step = max(1, int(math.ceil((max_c - min_c) / bins)))
            labels = [f"₹{min_c + i * step}..{min_c + (i + 1) * step}" for i in range(bins)]

            def _bucket(cost: int) -> str:
                if cost == max_c:
                    return labels[-1]
                idx = int((cost - min_c) / step)
                idx = max(0, min(bins - 1, idx))
                return labels[idx]

            hist_rows: Dict[str, Dict[str, int]] = {lab: {p: 0 for p in platforms} for lab in labels}
            for p in platforms:
                for cost in totals_by_platform.get(p, []):
                    hist_rows[_bucket(cost)][p] += 1

            hist_df = (
                pd.DataFrame.from_dict(hist_rows, orient="index")
                .reset_index(drop=False)
                .rename(columns={"index": "Range"})
            )
            st.bar_chart(hist_df.set_index("Range"))

    with tabs[2]:
        # Insights
        st.subheader("Weather guidance")
        if weather.condition == "Rainy":
            st.warning(weather_advice)
        elif weather.condition == "Cloudy":
            st.info(weather_advice)
        else:
            st.success(weather_advice)

        st.subheader("What-if: how much delay risk?")
        delay_risk = st.slider("Weather impact strength", 0.8, 1.5, 1.1, 0.05)
        # Apply an extra multiplier to time.
        weather_adj = get_weather(location=location)
        w2 = WeatherInfo(
            condition=weather_adj.condition,
            wait_minutes=weather_adj.wait_minutes,
            time_multiplier=weather_adj.time_multiplier * delay_risk,
            message=weather_adj.message,
        )

        tmp_quotes = platform_quotes
        tmp_quotes, tmp_advice = apply_weather_policy(tmp_quotes, w2)
        best2, _, reason2 = score_platforms(
            tmp_quotes,
            cost_weight=cost_w,
            time_weight=time_w,
            discount_weight=discount_w,
        )
        st.write(reason2)
        st.caption(tmp_advice)

