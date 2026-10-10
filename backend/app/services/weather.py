"""Weather via Open-Meteo (geocoding + hourly forecast, no API key).

forecast_for() never raises: on any problem it returns (None, notice) and the outfit
engine simply ignores the weather.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import settings
from app.schemas import WeatherOut
from app.services.rules import is_wet

log = logging.getLogger("stripefit.weather")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT = 8.0
CACHE_SECONDS = 15 * 60
FORECAST_DAYS = 16
NO_FORECAST = "No forecast available; outfit ignores weather."

# WMO weather codes -> (description, icon)
WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"), 3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"), 48: ("Freezing fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Heavy drizzle", "🌧️"),
    56: ("Freezing drizzle", "🌧️"), 57: ("Freezing drizzle", "🌧️"),
    61: ("Light rain", "🌦️"), 63: ("Rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
    66: ("Freezing rain", "🌧️"), 67: ("Freezing rain", "🌧️"),
    71: ("Light snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "❄️"), 77: ("Snow grains", "🌨️"),
    80: ("Rain showers", "🌦️"), 81: ("Rain showers", "🌧️"), 82: ("Violent showers", "⛈️"),
    85: ("Snow showers", "🌨️"), 86: ("Snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm with hail", "⛈️"), 99: ("Thunderstorm with hail", "⛈️"),
}

_cache: dict[str, tuple[float, Any]] = {}

# Demo switch (POST /api/debug/weather-override): pretend it's raining/hot so judges can see the
# weather rules on any day. None = real forecast.
OVERRIDE: dict[str, Any] | None = None
DEMO_WEATHER = {
    "rain": {"temperature_c": 9.0, "precipitation_probability": 85, "precipitation_mm": 1.8, "wind_kmh": 32.0, "weather_code": 63},
    "cold": {"temperature_c": 2.0, "precipitation_probability": 10, "precipitation_mm": 0.0, "wind_kmh": 12.0, "weather_code": 3},
    "hot": {"temperature_c": 25.0, "precipitation_probability": 0, "precipitation_mm": 0.0, "wind_kmh": 8.0, "weather_code": 0},
}


def _get_json(url: str, params: dict[str, Any]) -> Any:
    key = url + repr(sorted(params.items()))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    response = httpx.get(url, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    _cache[key] = (time.time(), data)
    return data


def geocode(name: str) -> tuple[str, float, float] | None:
    """Find a place, preferring Ireland. Returns (display name, lat, lon) or None."""
    for params in ({"name": name, "count": 1, "countryCode": "IE"}, {"name": name, "count": 1}):
        try:
            results = _get_json(GEOCODE_URL, params).get("results") or []
        except (httpx.HTTPError, ValueError):
            log.warning("Geocoding failed for %r", name)
            return None
        if results:
            place = results[0]
            label = ", ".join(p for p in (place.get("name"), place.get("admin1") or place.get("country")) if p)
            return label, float(place["latitude"]), float(place["longitude"])
    return None


def forecast_for(destination: str | None, when: datetime) -> tuple[WeatherOut | None, list[str]]:
    """Weather at the hour nearest `when` at the destination (or the default location)."""
    notices: list[str] = []
    tz = settings.tz
    when = when.astimezone(tz) if when.tzinfo else when.replace(tzinfo=tz)
    now = datetime.now(tz)
    if when < now - timedelta(hours=1):
        return None, ["That time has already passed. " + NO_FORECAST]
    if when > now + timedelta(days=FORECAST_DAYS - 1):
        return None, ["That's too far ahead for a forecast. " + NO_FORECAST]

    place = geocode(destination) if destination else None
    if place is None:
        if destination:
            notices.append(f"Using {settings.DEFAULT_LOCATION_NAME} weather for “{destination}”.")
        place = (settings.DEFAULT_LOCATION_NAME, settings.DEFAULT_LAT, settings.DEFAULT_LON)
    label, lat, lon = place

    if OVERRIDE is not None:
        return _weather_from(OVERRIDE, label, when), notices + ["Demo weather is on (set on the AI log page)."]

    try:
        data = _get_json(FORECAST_URL, {
            "latitude": round(lat, 3),
            "longitude": round(lon, 3),
            "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m,weather_code",
            "timezone": settings.TIMEZONE,
            "forecast_days": FORECAST_DAYS,
        })
        hourly = data["hourly"]
        times = [datetime.fromisoformat(t).replace(tzinfo=tz) for t in hourly["time"]]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("Forecast failed: %s", exc)
        return None, [NO_FORECAST]  # the location notice is moot without a forecast
    if not times:
        return None, [NO_FORECAST]  # the location notice is moot without a forecast

    i = min(range(len(times)), key=lambda k: abs(times[k] - when))
    temp = hourly["temperature_2m"][i]
    if temp is None:
        return None, [NO_FORECAST]  # the location notice is moot without a forecast
    rain_prob = hourly["precipitation_probability"][i]
    rain_mm = hourly["precipitation"][i]
    code = hourly["weather_code"][i]
    description, icon = WEATHER_CODES.get(code if code is not None else -1, ("Unknown conditions", "🌡️"))
    weather = WeatherOut(
        location_name=label,
        time=times[i].isoformat(),
        temperature_c=round(float(temp), 1),
        precipitation_probability=rain_prob,
        precipitation_mm=rain_mm,
        wind_kmh=hourly["wind_speed_10m"][i],
        weather_code=code,
        description=description,
        icon=icon,
        is_wet=is_wet(rain_prob, rain_mm),
    )
    return weather, notices


def _weather_from(values: dict[str, Any], label: str, when: datetime) -> WeatherOut:
    description, icon = WEATHER_CODES.get(values["weather_code"], ("Unknown conditions", "🌡️"))
    return WeatherOut(
        location_name=label,
        time=when.isoformat(),
        temperature_c=values["temperature_c"],
        precipitation_probability=values["precipitation_probability"],
        precipitation_mm=values["precipitation_mm"],
        wind_kmh=values["wind_kmh"],
        weather_code=values["weather_code"],
        description=description,
        icon=icon,
        is_wet=is_wet(values["precipitation_probability"], values["precipitation_mm"]),
    )
