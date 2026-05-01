from __future__ import annotations

import random
import re
from typing import Any, Dict, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


def _seed(platform: str, item_name: str, restaurant_name: str, location: str) -> int:
    raw = f"{platform}|{item_name}|{restaurant_name}|{location}"
    return abs(hash(raw)) % (2**32)


def _detect_base_price(item_name: str) -> int:
    s = item_name.lower()
    if any(k in s for k in ["biryani", "shawarma"]):
        return 228
    if any(k in s for k in ["pizza"]):
        return 265
    if any(k in s for k in ["burger"]):
        return 158
    if any(k in s for k in ["dosa", "idli", "vada"]):
        return 132
    if any(k in s for k in ["pasta"]):
        return 214
    if any(k in s for k in ["fried rice", "chowmein", "noodles"]):
        return 192
    if any(k in s for k in ["chicken", "mutton", "paneer"]):
        return 242
    return 202


def _simulate_quote(item_name: str, restaurant_name: str, location: str) -> Dict[str, Any]:
    rng = random.Random(_seed("Magicpin", item_name, restaurant_name, location))
    base = _detect_base_price(item_name)

    loc_factor = 1.0 + (rng.randint(-4, 14) / 100.0)
    item_price = max(80, int(round(base * loc_factor + rng.randint(-20, 65))))

    # Magicpin is often promo-driven; emulate modest-to-good discounts.
    discount = max(0, int(round(rng.uniform(5.0, 75.0))))

    delivery_fee = max(25, int(round(rng.uniform(20.0, 105.0) - (item_price / 1000.0 * 8.0))))
    taxes = max(0, int(round(item_price * rng.uniform(0.06, 0.13))))

    # Delivery estimates slightly in-between.
    delivery_time = max(14, int(round(rng.uniform(20.0, 50.0) + rng.uniform(-3.0, 7.0))))

    return {
        "platform": "Magicpin",
        "item_price": item_price,
        "delivery_fee": delivery_fee,
        "taxes": taxes,
        "discount": discount,
        "delivery_time": delivery_time,
        "data_source": "simulated",
    }


def _try_scrape_magicpin(item_name: str, restaurant_name: str, location: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort scraping attempt using requests + BeautifulSoup.

    In many environments Magicpin pages may render dynamically or block bots,
    so this function is intentionally conservative and returns None if it
    can't confidently extract price + discount + time.
    """

    query = f"{item_name} {restaurant_name}".strip()
    url = f"https://www.magicpin.in/search/?q={quote_plus(query)}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }

    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    price_match = re.search(r"₹\s*([0-9]{2,5})", text)
    discount_match = re.search(r"([0-9]{1,3})\s*%\s*(?:off|discount)", text, flags=re.IGNORECASE)
    if not discount_match:
        discount_match = re.search(r"([0-9]{1,3})\s*% ", text)

    # Delivery time is usually not shown on promo pages; if we can't find it, abort.
    time_match = re.search(r"([0-9]{1,3})\s*(?:min|mins|minutes)\b", text, flags=re.IGNORECASE)

    if not (price_match and discount_match and time_match):
        return None

    item_price = int(price_match.group(1))
    discount = int(discount_match.group(1))
    delivery_time = int(time_match.group(1))
    if item_price < 50 or delivery_time <= 0:
        return None

    delivery_fee = max(20, int(round(item_price * 0.16)))
    taxes = max(0, int(round(item_price * 0.09)))

    return {
        "platform": "Magicpin",
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
      "platform": "Magicpin",
      "item_price": 250,
      "delivery_fee": 40,
      "taxes": 18,
      "discount": 50,
      "delivery_time": 35
    }
    """

    try:
        scraped = _try_scrape_magicpin(item_name, restaurant_name, location)
        if scraped:
            return scraped
    except Exception:
        pass

    return _simulate_quote(item_name=item_name, restaurant_name=restaurant_name, location=location)

