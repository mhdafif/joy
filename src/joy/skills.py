"""Skills: folders with a SKILL.md that teach Joy a repeatable procedure."""

from dataclasses import dataclass
from pathlib import Path

from joy.settings import joy_home

BODY_LIMIT = 30_000


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path


def _parse(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    values: dict[str, str] = {}
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return values, "\n".join(lines[index + 1:]).strip()
        key, separator, value = lines[index].partition(":")
        if separator and not lines[index].startswith((" ", "\t")):
            values[key.strip()] = value.strip().strip("\"'")
    return {}, text


def skill_directories(root: Path) -> list[Path]:
    return [root / ".joy" / "skills", root / ".claude" / "skills", joy_home() / "skills"]


def discover(root: Path) -> dict[str, Skill]:
    found: dict[str, Skill] = {}
    for directory in skill_directories(root.resolve()):
        try:
            children = sorted(directory.iterdir())
        except OSError:
            continue
        for child in children:
            file = child / "SKILL.md"
            if not file.is_file():
                continue
            try:
                values, body = _parse(file.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            name = values.get("name") or child.name
            description = values.get("description") or next((line.strip() for line in body.splitlines() if line.strip()), "")
            found.setdefault(name, Skill(name, " ".join(description.split())[:200], file))
    return found


def load_body(skill: Skill) -> str:
    try:
        _, body = _parse(skill.path.read_text(encoding="utf-8", errors="replace"))
    except OSError as error:
        raise ValueError(f"Could not read the skill: {error}") from error
    return f"Skill folder: {skill.path.parent}\n\n{body[:BODY_LIMIT]}"

