"""Keyword-based request parser. Used as the fallback when the AI parse fails (and by mock mode).

It is intentionally simple and predictable: keyword lists for occasion and travel, a few
time phrases, and a capitalised place name after "in/at/to/near" as the destination.
"""

import re
from datetime import datetime, timedelta

from app.schemas import ParsedRequest

OCCASION_KEYWORDS: list[tuple[str, list[str]]] = [  # first match wins, so specific occasions go first
    ("interview", ["interview", "assessment centre"]),
    ("debs", ["debs", "ball", "gala", "formal"]),
    ("wedding", ["wedding", "reception", "black tie"]),
    ("funeral", ["funeral", "memorial", "removal", "wake"]),
    ("presentation", ["presentation", "presenting", "pitch", "giving a talk", "viva"]),
    ("festival", ["festival", "electric picnic", "longitude", "forbidden fruit"]),
    ("match", ["watching the match", "watch the match", "at the match", "to the match", "watching the game",
               "croke park", "aviva", "stadium", "match day"]),
    ("sport", ["football", "soccer", "training", "gym", "running", "run", "match", "rugby", "gaa", "hurling",
               "camogie", "tennis", "basketball", "swim", "swimming", "yoga", "hike", "hiking", "5k", "parkrun"]),
    ("travel", ["flight", "flying", "airport", "travel", "travelling", "traveling", "road trip", "ferry"]),
    ("society", ["society", "societies", "soc event"]),
    ("night_out", ["night out", "club", "clubbing", "pub", "pints", "drinks", "party", "going out", "gig", "concert"]),
    ("date", ["date", "dinner date"]),
    ("work", ["work", "office", "shift", "internship", "placement", "job"]),
    ("uni", ["uni", "lecture", "lectures", "college", "campus", "class", "tutorial", "lab", "library", "seminar",
             "ucd", "tcd", "trinity", "dcu", "tu dublin", "maynooth"]),
    ("casual", ["casual", "coffee", "shopping", "cinema", "brunch", "lunch", "friends", "chill", "walk", "errands",
                "day off", "everyday"]),
]

SETTING_KEYWORDS: list[tuple[str, list[str]]] = [
    ("outdoor", ["outdoor", "outdoors", "outside", "festival", "stadium", "match", "hike", "hiking", "park", "beach",
                 "picnic", "garden", "beer garden"]),
    ("indoor", ["indoor", "indoors", "inside", "cinema", "office", "lecture", "library", "restaurant", "theatre"]),
]
ACTIVITY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("dancing", ["dancing", "dance", "clubbing", "club", "debs", "ball"]),
    ("active", ["football", "gym", "running", "training", "hike", "hiking", "tennis", "swim", "yoga"]),
    ("standing", ["gig", "concert", "festival", "match", "standing", "queue"]),
    ("walking", ["walking", "walk", "tour", "sightseeing"]),
    ("sitting", ["lecture", "cinema", "flight", "exam", "dinner", "meeting", "class"]),
]
ALL_DAY_HOURS, ALL_NIGHT_HOURS = 10, 6

TRAVEL_KEYWORDS: list[tuple[str, list[str]]] = [
    ("walk", ["walk", "walking", "on foot"]),
    ("cycle", ["cycle", "cycling", "bike", "biking", "dublin bikes"]),
    ("bus", ["bus"]),
    ("train", ["train", "dart", "luas", "tram"]),
    ("car", ["car", "drive", "driving", "lift", "taxi", "uber", "freenow"]),
]

DEFAULT_HOUR: dict[str, tuple[int, int]] = {
    "night_out": (21, 0), "sport": (19, 0), "uni": (9, 0), "interview": (10, 0), "work": (9, 0),
    "wedding": (14, 0), "funeral": (11, 0), "date": (19, 30),
}
PART_OF_DAY: dict[str, tuple[int, int]] = {
    "morning": (9, 0), "noon": (12, 0), "midday": (12, 0), "lunchtime": (12, 30), "afternoon": (14, 0),
    "evening": (19, 0), "tonight": (20, 0),
}
DRESS_CODES = ["black tie", "smart casual", "business casual", "cocktail", "formal", "casual"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
NOT_PLACES = set(WEEKDAYS) | {"january", "february", "march", "april", "may", "june", "july", "august",
                              "september", "october", "november", "december", "the", "my"}
# Capitalised words that end a place name rather than belong to it ("Temple Bar Saturday" -> "Temple Bar").
TIME_WORDS = NOT_PLACES | {"today", "tonight", "tomorrow", "next", "this", "morning", "afternoon", "evening", "noon"}


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _first_match(text: str, table: list[tuple[str, list[str]]], default: str) -> str:
    for value, words in table:
        if any(_has(text, w) for w in words):
            return value
    return default


def _resolve_time(text: str, occasion: str, now: datetime) -> datetime:
    day = now.date()
    explicit_day = False
    if _has(text, "tomorrow"):
        day, explicit_day = day + timedelta(days=1), True
    else:
        for index, name in enumerate(WEEKDAYS):
            if _has(text, name):
                day, explicit_day = day + timedelta(days=(index - now.weekday()) % 7), True
                break

    hour_minute: tuple[int, int] | None = None
    clock = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)\b", text)
    at_hour = re.search(r"\bat\s+(\d{1,2})(?:[:.](\d{2}))?\b", text)
    if clock:
        hour = int(clock.group(1)) % 12 + (12 if clock.group(3) == "pm" else 0)
        hour_minute = (hour, int(clock.group(2) or 0))
    elif at_hour and int(at_hour.group(1)) <= 23:
        hour = int(at_hour.group(1))
        if hour < 8 and (occasion in ("night_out", "date", "sport") or _has(text, "tonight")):
            hour += 12  # "drinks at 8" means 20:00
        hour_minute = (hour, int(at_hour.group(2) or 0))
    else:
        for phrase, hm in PART_OF_DAY.items():
            if _has(text, phrase):
                hour_minute = hm
                break
    if hour_minute is None:
        hour_minute = DEFAULT_HOUR.get(occasion)
    if hour_minute is None:  # casual / other with no time: about an hour from now
        soon = now + timedelta(hours=1)
        return soon.replace(minute=0, second=0, microsecond=0)

    when = datetime(day.year, day.month, day.day, *hour_minute, tzinfo=now.tzinfo)
    if when < now - timedelta(minutes=30) and not explicit_day:
        when += timedelta(days=1)  # never plan for a time that has already passed today
    return when


def _destination(original: str) -> str | None:
    pattern = r"\b(?:in|at|to|near|around)\s+((?:[A-Z][\w'’-]*)(?:\s+(?:[A-Z][\w'’-]*|of|the))*)"
    for match in re.finditer(pattern, original):
        words = match.group(1).split()
        while words and words[-1].lower() in TIME_WORDS:
            words.pop()
        place = re.sub(r"\s+(of|the)$", "", " ".join(words)).strip()
        if not place:
            continue
        if place.lower() not in NOT_PLACES:
            return place
    return None


def _duration(text: str) -> float | None:
    """'for 3 hours', '2h', 'all day', 'all night'. Otherwise None (the occasion default applies)."""
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", text)
    if match:
        return float(match.group(1))
    if "all day" in text:
        return ALL_DAY_HOURS
    if "all night" in text:
        return ALL_NIGHT_HOURS
    return None


def parse_request_rules(request_text: str, now: datetime) -> ParsedRequest:
    original = request_text.strip()
    text = original.lower()
    words = re.findall(r"[a-zA-Z]{2,}", text)
    occasion = _first_match(text, OCCASION_KEYWORDS, "other")

    if not words or (len(words) == 1 and occasion == "other"):
        return ParsedRequest(
            occasion="other",
            datetime_iso=now.isoformat(timespec="minutes"),
            needs_clarification="Where are you heading, and when? e.g. 'Lectures at UCD tomorrow, cycling'.",
        )

    dress_code = next((code for code in DRESS_CODES if _has(text, code)), None)
    return ParsedRequest(
        setting=_first_match(text, SETTING_KEYWORDS, "unknown"),  # type: ignore[arg-type]
        activity=_first_match(text, ACTIVITY_KEYWORDS, "unknown"),  # type: ignore[arg-type]
        duration_hours=_duration(text),
        occasion=occasion,  # type: ignore[arg-type]
        occasion_detail=original[:80],
        destination=_destination(original),
        datetime_iso=_resolve_time(text, occasion, now).isoformat(timespec="minutes"),
        travel_mode=_first_match(text, TRAVEL_KEYWORDS, "unknown"),  # type: ignore[arg-type]
        dress_code=dress_code,
    )
