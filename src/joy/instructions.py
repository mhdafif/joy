"""Project instructions: AGENTS.md or CLAUDE.md files that guide Joy in a folder."""

from pathlib import Path

from joy.settings import joy_home

FILE_NAMES = ("AGENTS.md", "CLAUDE.md")
FILE_LIMIT = 20_000
TOTAL_LIMIT = 40_000


def _git_root(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        if (directory / ".git").exists():
            return directory
    return None


def _first_file(directory: Path) -> Path | None:
    for name in FILE_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def find_instruction_files(root: Path) -> list[Path]:
    root = root.resolve()
    boundary = _git_root(root)
    directories = [root]
    if boundary is not None:
        directories = [directory for directory in (root, *root.parents) if directory == boundary or boundary in directory.parents]
    files: list[Path] = []
    global_file = _first_file(joy_home())
    if global_file is not None:
        files.append(global_file)
    for directory in reversed(directories):
        found = _first_file(directory)
        if found is not None:
            files.append(found)
    return files


def load_instructions(root: Path) -> tuple[str, list[Path]]:
    files = find_instruction_files(root)
    sections: list[str] = []
    used = 0
    included: list[Path] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if not text:
            continue
        text = text[:FILE_LIMIT]
        if used + len(text) > TOTAL_LIMIT:
            break
        used += len(text)
        sections.append(f"From {path}:\n{text}")
        included.append(path)
    return "\n\n".join(sections), included
