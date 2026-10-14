"""Readable lines and summaries for the steps Joy takes."""

from rich.console import Console, ConsoleOptions, RenderableType, RenderResult
from rich.padding import Padding
from rich.text import Text

TOOL_GLYPHS = {"read": ("→", "Read"), "write": ("←", "Write"), "edit": ("←", "Edit"), "bash": ("$", "")}
VERBS = {"read": "read", "write": "wrote", "edit": "edited"}


def render_tool(step: dict, indent: int = 1) -> RenderableType:
    glyph, label = TOOL_GLYPHS.get(step["name"], ("◆", step["name"]))
    failed = step.get("status") == "failed"
    line = Text()
    line.append(("✗" if failed else glyph) + " ", style="red" if failed else "cyan")
    if label:
        line.append(label + " ", style="bold")
    line.append(step.get("detail", ""))
    if failed and step.get("error"):
        line.append(" — " + step["error"], style="red")
    return Padding(line, (0, 0, 0, indent))


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def summarize(steps: list[dict]) -> str:
    phrases: list[str] = []
    for name, verb in VERBS.items():
        paths = list(dict.fromkeys(step.get("detail") or "a file" for step in steps if step["name"] == name))
        if paths:
            phrases.append(f"{verb} {paths[0]}" if len(paths) == 1 else f"{verb} {len(paths)} files")
    commands = sum(1 for step in steps if step["name"] == "bash")
    if commands:
        phrases.append("ran " + _plural(commands, "command"))
    others = sum(1 for step in steps if step["name"] not in TOOL_GLYPHS)
    if others:
        phrases.append("used " + _plural(others, "other tool"))
    if not phrases:
        return "Working"
    sentence = phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + " and " + phrases[-1]
    return sentence[0].upper() + sentence[1:]


class StepGroup:
    def __init__(self, expanded: bool = False, steps: list[dict] | None = None) -> None:
        self.expanded = expanded
        self.steps = list(steps or [])

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        line = Text(" ")
        line.append("▾ " if self.expanded else "▸ ", style="cyan")
        line.append(summarize(self.steps))
        failed = sum(1 for step in self.steps if step.get("status") == "failed")
        if failed:
            line.append(f" · {failed} failed", style="red")
        if not self.expanded:
            line.append("  ctrl+o to expand", style="dim")
        yield line
        if self.expanded:
            for step in self.steps:
                yield render_tool(step, indent=3)
