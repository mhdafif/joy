"""User settings stored next to saved sessions."""

import json
import os
import tempfile
from pathlib import Path


def joy_home() -> Path:
    return Path(os.environ.get("JOY_HOME") or Path.home() / ".joy")


def load_settings() -> dict:
    try:
        values = json.loads((joy_home() / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return values if isinstance(values, dict) else {}


def save_settings(values: dict) -> None:
    directory = joy_home()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False, encoding="utf-8") as file:
            temporary = Path(file.name)
            json.dump(values, file, ensure_ascii=False, indent=2)
        temporary.chmod(0o600)
        temporary.replace(directory / "settings.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
