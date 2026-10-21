"""Let terminals tell Shift+Enter apart from Enter."""

import string

from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.keys import Keys

ENABLE = "\x1b[>1u"
DISABLE = "\x1b[<u"
NEWLINE = (Keys.Escape, Keys.ControlM)
SHIFT, ALT, CTRL = 2, 3, 5


def sequences() -> dict:
    found: dict = {
        "\x1b[27;2;13~": NEWLINE,
        f"\x1b[13;{SHIFT}u": NEWLINE,
        f"\x1b[13;{ALT}u": NEWLINE,
        f"\x1b[13;{CTRL}u": Keys.ControlJ,
        f"\x1b[9;{SHIFT}u": Keys.BackTab,
        "\x1b[27u": Keys.Escape,
        f"\x1b[32;{CTRL}u": Keys.ControlAt,
    }
    for letter in string.ascii_lowercase:
        found[f"\x1b[{ord(letter)};{CTRL}u"] = getattr(Keys, f"Control{letter.upper()}")
        found[f"\x1b[{ord(letter)};{ALT}u"] = (Keys.Escape, letter)
    return found


def register() -> None:
    ANSI_SEQUENCES.update(sequences())
