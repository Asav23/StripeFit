"""Read and update single values in backend/.env without printing them (shared by setup scripts)."""

import re
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def read_env_value(name: str, path: Path = ENV_PATH) -> str:
    match = re.search(rf"^{name}=(.*)$", path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1).strip() if match else ""


def write_env_value(name: str, value: str, path: Path = ENV_PATH) -> None:
    text = path.read_text(encoding="utf-8")
    line = f"{name}={value}"
    if re.search(rf"^{name}=", text, re.MULTILINE):
        text = re.sub(rf"^{name}=.*$", lambda _: line, text, flags=re.MULTILINE)
    else:
        text = text.rstrip("\n") + f"\n{line}\n"
    path.write_text(text, encoding="utf-8")
