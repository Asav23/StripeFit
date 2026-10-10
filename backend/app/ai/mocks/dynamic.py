"""Mock generators for tasks whose output has to reflect the input.

They reuse the deterministic rule-based logic (the same code that powers the real
fallbacks) and dress it up like a model reply, so the mock UI behaves realistically.
"""

from datetime import datetime
from typing import Any, Callable


def parse_request(mock_input: dict[str, Any]) -> dict[str, Any]:
    from app.services.request_rules import parse_request_rules

    parsed = parse_request_rules(mock_input["text"], datetime.fromisoformat(mock_input["now"]))
    return parsed.model_dump()


def pick_outfit(mock_input: dict[str, Any]) -> dict[str, Any]:
    from app.services.outfit_engine import rule_based_pick

    picks = rule_based_pick(mock_input["candidates"], mock_input["parsed"], mock_input["requirements"])
    by_id = {c["id"]: c for c in mock_input["candidates"]}
    names = [by_id[i]["name"].lower() for i in _ids(picks) if i in by_id]
    occasion = mock_input["parsed"].get("occasion", "other").replace("_", " ")
    weather = mock_input.get("weather")
    if weather:
        weather_bit = f"{round(weather['temperature_c'])}°C and {weather['description'].lower()}"
        if weather.get("is_wet"):
            weather_bit += ", so staying dry matters"
    else:
        weather_bit = "no forecast, so I kept it versatile"
    explanation = f"For your {occasion}: {', '.join(names)}. It's {weather_bit}. The colours sit well together."
    return {**picks, "explanation": explanation, "confidence": 0.8}


def _ids(picks: dict[str, Any]) -> list[int]:
    ids = [picks.get(k) for k in ("top_id", "bottom_id", "one_piece_id", "outerwear_id", "shoes_id")]
    return [i for i in ids if i] + list(picks.get("accessory_ids") or [])


GENERATORS: dict[str, Callable[[Any], Any]] = {
    "parse_request": parse_request,
    "pick_outfit": pick_outfit,
}
