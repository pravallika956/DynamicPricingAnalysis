from __future__ import annotations

import random
import re
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


def _seed(platform: str, item_name: str, restaurant_name: str, location: str) -> int:
    # Deterministic pseudo-randomness per input (so UI stays stable).
    raw = f"{platform}|{item_name}|{restaurant_name}|{location}"
    return abs(hash(raw)) % (2**32)


def _detect_base_price(item_name: str) -> int:
    s = item_name.lower()
    if any(k in s for k in ["biryani", "shawarma"]):
        return 220
    if any(k in s for k in ["pizza"]):
        return 260
    if any(k in s for k in ["burger"]):
        return 160
    if any(k in s for k in ["dosa", "idli", "vada"]):
        return 130
    if any(k in s for k in ["pasta"]):
        return 210
    if any(k in s for k in ["fried rice", "chowmein", "noodles"]):
        return 190
    if any(k in s for k in ["chicken", "mutton", "paneer"]):
        return 240
    return 200


def _simulate_quote(item_name: str, restaurant_name: str, location: str) -> Dict[str, Any]:
    rng = random.Random(_seed("Zomato", item_name, restaurant_name, location))
    base = _detect_base_price(item_name)

    # Location influence (very rough, just to tailor numbers by city/pincode string).
    loc_factor = 1.0 + (rng.randint(-6, 12) / 100.0)
    item_price = max(80, int(round(base * loc_factor + rng.randint(-25, 70))))

    # Zomato tends to offer more discounts in practice; we emulate that slightly.
    discount = max(0, int(round(rng.uniform(0.0, 85.0))))

    # Delivery fee is sometimes higher when cart value is lower.
    delivery_fee = max(20, int(round(rng.uniform(25.0, 95.0) - (item_price / 1000.0 * 15.0))))

    # Taxes are estimated as a percentage of the item price.
    tax_rate = rng.uniform(0.05, 0.12)
    taxes = max(0, int(round(item_price * tax_rate)))

    # Delivery time in minutes.
    delivery_time = max(15, int(round(rng.uniform(25.0, 55.0) + rng.uniform(-3.0, 8.0))))

    return {
        "platform": "Zomato",
        "item_price": item_price,
        "delivery_fee": delivery_fee,
        "taxes": taxes,
        "discount": discount,
        "delivery_time": delivery_time,
        "data_source": "simulated",
    }


def _try_scrape_zomato(item_name: str, restaurant_name: str, location: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort scraping attempt using requests + BeautifulSoup.

    Real-world scraping for Zomato often breaks due to dynamic rendering / bot protections.
    This function intentionally fails safely (returns None) and falls back to simulation.
    """

    # Use location loosely: Zomato URL structure depends on city slug.
    # We'll try a generic path; if parsing fails, caller falls back.
    city_guess = re.sub(r"[^a-zA-Z]", " ", location).strip().split()
    city_slug = (city_guess[0] if city_guess else "india").lower()

    query = f"{item_name} {restaurant_name}".strip()
    url = f"https://www.zomato.com/{city_slug}/search?q={quote_plus(query)}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    # Heuristic extraction from rendered/embedded text.
    # We only accept results if we can find a plausible price + time + discount.
    price_match = re.search(r"₹\s*([0-9]{2,5})", text)
    time_match = re.search(r"([0-9]{1,3})\s*(?:min|mins|minutes)\b", text, flags=re.IGNORECASE)

    discount_match = re.search(r"([0-9]{1,3})\s*%\s*off\b", text, flags=re.IGNORECASE)
    if not discount_match:
        # Some pages use "OFF" or "Save" patterns; keep this loose.
        discount_match = re.search(r"\b([0-9]{1,3})\s*%?\s*off\b", text, flags=re.IGNORECASE)

    if not (price_match and time_match):
        return None

    item_price = int(price_match.group(1))
    delivery_time = int(time_match.group(1))
    discount = int(discount_match.group(1)) if discount_match else 0

    # Delivery fee and taxes are not reliably parseable from search HTML;
    # if missing, we compute reasonable estimates from item price.
    delivery_fee_match = re.search(r"delivery\s*fee\s*₹\s*([0-9]{1,4})", text, flags=re.IGNORECASE)
    delivery_fee = int(delivery_fee_match.group(1)) if delivery_fee_match else max(20, int(round(item_price * 0.18)))

    tax_rate = 0.08
    taxes = max(0, int(round(item_price * tax_rate)))

    # Defensive bounds.
    if item_price < 50 or delivery_time <= 0:
        return None

    return {
        "platform": "Zomato",
        "item_price": item_price,
        "delivery_fee": delivery_fee,
        "taxes": taxes,
        "discount": discount,
        "delivery_time": delivery_time,
        "data_source": "scraped",
    }


def fetch_quote(item_name: str, restaurant_name: str, location: str) -> Dict[str, Any]:
    """
    Returns a normalized quote for the decision engine.

    Output schema:
    {
      "platform": "Zomato",
      "item_price": 250,
      "delivery_fee": 40,
      "taxes": 18,
      "discount": 50,
      "delivery_time": 35
    }
    """

    try:
        scraped = _try_scrape_zomato(item_name, restaurant_name, location)
        if scraped:
            return scraped
    except Exception:
        # Scraping restrictions vary; fall back seamlessly.
        pass

    return _simulate_quote(item_name=item_name, restaurant_name=restaurant_name, location=location)

