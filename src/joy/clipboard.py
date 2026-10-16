"""Copy text to the system clipboard."""

import base64
import shutil
import subprocess
import sys

COMMANDS = {
    "darwin": [["pbcopy"]],
    "win32": [["clip"]],
}
LINUX_COMMANDS = [["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]


def copy_text(text: str) -> bool:
    for command in COMMANDS.get(sys.platform, LINUX_COMMANDS):
        if shutil.which(command[0]) is None:
            continue
        try:
            subprocess.run(command, input=text.encode("utf-8"), timeout=2, check=True)
        except (OSError, subprocess.SubprocessError):
            continue
        return True
    return False


def osc52(text: str) -> str:
    return "\x1b]52;c;" + base64.b64encode(text.encode("utf-8")).decode("ascii") + "\x07"
