from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class WeatherInfo:
    condition: str  # "Rainy", "Cloudy", "Clear"
    wait_minutes: int
    time_multiplier: float
    message: str


def _seed_from_text(text: str) -> int:
    # Deterministic seed so the same location gives the same weather prediction.
    raw = (text or "").strip().lower()
    return abs(hash(raw)) % (2**32)


def get_weather(location: str) -> WeatherInfo:
    """
    Simulated weather based on the provided location.

    We simulate because adding a real weather API usually requires keys
    and additional setup. This is deterministic so the UI stays stable.
    """

    seed = _seed_from_text(location)
    rng = random.Random(seed)

    # Simple probabilities tuned for India (more likely rainy in some locations/seeds).
    r = rng.random()
    if r < 0.33:
        condition = "Rainy"
        time_multiplier = 1.2
        wait_minutes = rng.randint(8, 18)
        message = "Rainy conditions can slow delivery; waiting briefly can help."
    elif r < 0.7:
        condition = "Cloudy"
        time_multiplier = 1.08
        wait_minutes = rng.randint(3, 10)
        message = "Cloudy conditions may cause minor delays."
    else:
        condition = "Clear"
        time_multiplier = 1.0
        wait_minutes = 0
        message = "Weather looks fine; delivery time is likely closer to estimates."

    return WeatherInfo(
        condition=condition,
        wait_minutes=int(wait_minutes),
        time_multiplier=float(time_multiplier),
        message=message,
    )


def apply_weather_policy(
    quotes: List[Dict[str, Any]],
    weather: WeatherInfo,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Adjust delivery time estimates based on weather.
    """

    adjusted = []
    for q in quotes:
        qq = q.copy()
        old_time = float(qq.get("delivery_time", 0) or 0)
        if old_time <= 0:
            new_time = old_time
        else:
            new_time = int(math.ceil(old_time * weather.time_multiplier))
        qq["delivery_time"] = new_time
        qq["weather_condition"] = weather.condition
        qq["weather_time_multiplier"] = weather.time_multiplier
        adjusted.append(qq)

    if weather.condition == "Rainy":
        ui_advice = f"it is rainy in your area; consider waiting ~{weather.wait_minutes} minutes."
    elif weather.condition == "Cloudy":
        ui_advice = f"it is cloudy in your area; you can wait ~{weather.wait_minutes} minutes for smoother delivery."
    else:
        ui_advice = "weather is clear; you can order now."

    return adjusted, ui_advice

