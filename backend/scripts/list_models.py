"""List OpenRouter models with price and capabilities, to help choose MODEL_* values.

Public endpoint, no key needed.  .venv/bin/python scripts/list_models.py [filter]
"""

import sys

import httpx

URL = "https://openrouter.ai/api/v1/models"


def main() -> None:
    term = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    models = httpx.get(URL, timeout=20).json()["data"]
    print(f"{'model':55} {'$/M in':>8} {'$/M out':>8}  image  json")
    for m in sorted(models, key=lambda m: m["id"]):
        if term not in m["id"].lower() or m["id"].endswith(":batch"):
            continue
        pricing = m.get("pricing", {})
        image = "image" in m.get("architecture", {}).get("input_modalities", [])
        json_ok = "response_format" in m.get("supported_parameters", [])
        print(f"{m['id']:55} {float(pricing.get('prompt', 0)) * 1e6:8.3f} {float(pricing.get('completion', 0)) * 1e6:8.3f}"
              f"  {'yes' if image else '-':5}  {'yes' if json_ok else '-'}")


if __name__ == "__main__":
    main()
