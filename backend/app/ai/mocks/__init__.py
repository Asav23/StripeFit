"""Mock AI mode (USE_MOCK_AI=true): realistic fixtures, zero network calls.

Fixture lookup for a task:
  1. a forced override set via POST /api/debug/mock-override ("error" simulates an outage,
     any other value loads `{task}.{variant}.json`);
  2. a dynamic generator in dynamic.py (for tasks whose output must reference the input,
     e.g. outfit picks must use real candidate IDs);
  3. `{task}.json`: a single object, a list (picked by a stable hash of the input, so the
     same photo always gets the same labels) or {"cases": [{"match", "response"}], "default"}.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

MOCK_DIR = Path(__file__).resolve().parent
MOCK_LATENCY_SECONDS = 0.4

OVERRIDES: dict[str, str] = {}  # task -> variant


class MockFailure(Exception):
    pass


def available_variants() -> dict[str, list[str]]:
    variants: dict[str, list[str]] = {}
    for path in MOCK_DIR.glob("*.*.json"):
        task, variant, _ = path.name.split(".")
        variants.setdefault(task, []).append(variant)
    return variants


def load(task: str, mock_input: Any) -> Any:
    variant = OVERRIDES.get(task)
    if variant == "error":
        raise MockFailure("forced mock failure")
    if variant:
        return _read(f"{task}.{variant}.json")

    from app.ai.mocks import dynamic  # lazy: dynamic mocks reuse service logic

    generator = dynamic.GENERATORS.get(task)
    if generator:
        return generator(mock_input)
    return _select(_read(f"{task}.json"), mock_input)


def _read(filename: str) -> Any:
    path = MOCK_DIR / filename
    if not path.exists():
        raise MockFailure(f"no mock fixture {filename}")
    return json.loads(path.read_text())


def _stable_index(value: Any, size: int) -> int:
    digest = hashlib.sha1(str(value).encode()).hexdigest()
    return int(digest, 16) % size


def _select(data: Any, mock_input: Any) -> Any:
    if isinstance(data, list):
        return data[_stable_index(mock_input, len(data))]
    if isinstance(data, dict) and "cases" in data:
        text = str(mock_input or "").lower()
        for case in data["cases"]:
            if case["match"].lower() in text:
                return case["response"]
        return data["default"]
    return data
