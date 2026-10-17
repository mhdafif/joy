"""Show the working folder in a small space and open it in the file manager."""

import subprocess
import sys
from pathlib import Path

from prompt_toolkit.utils import get_cwidth

OPENERS = {
    "darwin": ["open"],
    "win32": ["explorer"],
}
LINUX_OPENER = ["xdg-open"]


def shorten_folder(path: str, room: int) -> str:
    if get_cwidth(path) <= room:
        return path
    lead = "~/" if path.startswith("~") else "/"
    parts = [part for part in path.split("/") if part and part != "~"]
    if not parts:
        return path[:max(room, 1)]
    tail = parts[-1]
    for part in reversed(parts[:-1]):
        candidate = f"{part}/{tail}"
        if get_cwidth(f"{lead}…/{candidate}") > room:
            break
        tail = candidate
    shortened = f"{lead}…/{tail}"
    if get_cwidth(shortened) <= room:
        return shortened
    kept = shortened
    while get_cwidth("…" + kept) > room and len(kept) > 1:
        kept = kept[1:]
    return "…" + kept


def open_folder(path: Path) -> bool:
    command = [*OPENERS.get(sys.platform, LINUX_OPENER), str(path)]
    try:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return False
    return True
