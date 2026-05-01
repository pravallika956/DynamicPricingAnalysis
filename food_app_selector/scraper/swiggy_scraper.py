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
        return 235
    if any(k in s for k in ["pizza"]):
        return 270
    if any(k in s for k in ["burger"]):
        return 165
    if any(k in s for k in ["dosa", "idli", "vada"]):
        return 135
    if any(k in s for k in ["pasta"]):
        return 220
    if any(k in s for k in ["fried rice", "chowmein", "noodles"]):
        return 200
    if any(k in s for k in ["chicken", "mutton", "paneer"]):
        return 245
    return 205


def _simulate_quote(item_name: str, restaurant_name: str, location: str) -> Dict[str, Any]:
    rng = random.Random(_seed("Swiggy", item_name, restaurant_name, location))
    base = _detect_base_price(item_name)

    # Swiggy often shows slightly higher base prices, but faster delivery (emulated here).
    loc_factor = 1.0 + (rng.randint(-5, 10) / 100.0)
    item_price = max(80, int(round(base * loc_factor + rng.randint(-20, 65))))

    # Discount is generally smaller than Zomato in many cases; emulate lower discounts.
    discount = max(0, int(round(rng.uniform(0.0, 60.0))))

    delivery_fee = max(25, int(round(rng.uniform(30.0, 110.0) - (item_price / 1000.0 * 10.0))))

    tax_rate = rng.uniform(0.05, 0.13)
    taxes = max(0, int(round(item_price * tax_rate)))

    delivery_time = max(12, int(round(rng.uniform(22.0, 45.0) + rng.uniform(-3.0, 6.0))))

    return {
        "platform": "Swiggy",
        "item_price": item_price,
        "delivery_fee": delivery_fee,
        "taxes": taxes,
        "discount": discount,
        "delivery_time": delivery_time,
        "data_source": "simulated",
    }


def _try_scrape_swiggy(item_name: str, restaurant_name: str, location: str) -> Optional[Dict[str, Any]]:
    """
    Best-effort scraping attempt for Swiggy via requests + BeautifulSoup.

    If scraping fails (commonly due to bot checks / dynamic content), return None.
    """

    query = f"{item_name} {restaurant_name}".strip()
    url = f"https://www.swiggy.com/search?q={quote_plus(query)}"

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
    time_match = re.search(r"([0-9]{1,3})\s*(?:min|mins|minutes)\b", text, flags=re.IGNORECASE)

    discount_match = re.search(r"([0-9]{1,3})\s*%\s*off\b", text, flags=re.IGNORECASE)
    if not discount_match:
        discount_match = re.search(r"\b([0-9]{1,3})\s*%?\s*off\b", text, flags=re.IGNORECASE)

    if not (price_match and time_match):
        return None

    item_price = int(price_match.group(1))
    delivery_time = int(time_match.group(1))
    discount = int(discount_match.group(1)) if discount_match else 0

    delivery_fee_match = re.search(r"delivery\s*fee\s*₹\s*([0-9]{1,4})", text, flags=re.IGNORECASE)
    delivery_fee = int(delivery_fee_match.group(1)) if delivery_fee_match else max(25, int(round(item_price * 0.19)))

    taxes = max(0, int(round(item_price * 0.08)))

    if item_price < 50 or delivery_time <= 0:
        return None

    return {
        "platform": "Swiggy",
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
      "platform": "Swiggy",
      "item_price": 250,
      "delivery_fee": 40,
      "taxes": 18,
      "discount": 50,
      "delivery_time": 35
    }
    """

    try:
        scraped = _try_scrape_swiggy(item_name, restaurant_name, location)
        if scraped:
            return scraped
    except Exception:
        pass

    return _simulate_quote(item_name=item_name, restaurant_name=restaurant_name, location=location)

