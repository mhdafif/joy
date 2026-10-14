"""Render file changes as syntax-highlighted diff panels for the terminal."""

from difflib import SequenceMatcher

from rich import box
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Span, Text

from joy.tools import Change

COLLAPSED_LINES = 20
NO_EOL = "\x00"
NO_EOL_NOTE = "  ⏎ no newline at end of file"
CONTEXT_LINES = 3
HIGHLIGHT_LIMIT = 200_000
PANEL_BACKGROUND = "#1a1a1a"
BORDER = "#3a3a3a"
ROW_STYLES = {"+": "on #12353a", "-": "on #3b1b21", " ": ""}
SIGN_STYLES = {"+": "bold #4ade80", "-": "bold #f87171", " ": ""}
NUMBER_STYLES = {"+": "#9ca3af", "-": "#9ca3af", " ": "#5b6270"}
GAP = "⋯"
LABELS = {"created": "Created", "modified": "Modified"}

Row = tuple[int | None, str, str]


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _lines(text: str) -> list[str]:
    lines = _normalize(text).split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    elif lines:
        lines[-1] += NO_EOL
    return lines


def _highlight(path: str, text: str) -> list[Text] | None:
    code = _normalize(text)
    if not code or len(code) > HIGHLIGHT_LIMIT:
        return None
    try:
        syntax = Syntax(code, Syntax.guess_lexer(path, code), theme="monokai",
                        background_color="default")
        highlighted = syntax.highlight(code)
    except Exception:
        return None
    highlighted.spans = [
        Span(span.start, span.end, Style(
            color=span.style.color, bold=span.style.bold,
            italic=span.style.italic, underline=span.style.underline,
        ))
        for span in highlighted.spans if isinstance(span.style, Style)
    ]
    highlighted.style = ""
    highlighted.expand_tabs(4)
    return highlighted.split("\n")


def _rows(change: Change) -> list[Row]:
    new = _lines(change.after)
    if change.kind == "created":
        return [(number, "+", line) for number, line in enumerate(new, 1)]
    old = _lines(change.before)
    rows: list[Row] = []
    matcher = SequenceMatcher(None, old, new, autojunk=False)
    for group in matcher.get_grouped_opcodes(CONTEXT_LINES):
        if rows:
            rows.append((None, GAP, ""))
        for tag, old_start, old_end, new_start, new_end in group:
            if tag == "equal":
                rows.extend((new_start + offset + 1, " ", new[new_start + offset])
                            for offset in range(new_end - new_start))
                continue
            if tag in ("replace", "delete"):
                rows.extend((old_start + offset + 1, "-", old[old_start + offset])
                            for offset in range(old_end - old_start))
            if tag in ("replace", "insert"):
                rows.extend((new_start + offset + 1, "+", new[new_start + offset])
                            for offset in range(new_end - new_start))
    return rows


def merge_changes(changes: list[Change]) -> list[Change]:
    merged: dict[str, Change] = {}
    for change in changes:
        first = merged.get(change.path)
        merged[change.path] = change if first is None else Change(
            change.path, first.kind, first.before, change.after,
        )
    return list(merged.values())


def render_change(change: Change, number: int, limit: int | None = COLLAPSED_LINES) -> tuple[Panel, int]:
    rows = _rows(change)
    added = sum(1 for _, sign, _ in rows if sign == "+")
    removed = sum(1 for _, sign, _ in rows if sign == "-")
    title = Text.assemble(
        (f"{LABELS[change.kind]} ", "bold"), (change.path, "cyan"),
        (f"  +{added}", "green"), *([(f" −{removed}", "red")] if removed else []),
    )
    shown = rows if limit is None else rows[:limit]
    hidden = len(rows) - len(shown)
    subtitle = Text(f"… {hidden} more lines · /expand {number}", style="dim") if hidden else None
    if not rows:
        message = "(no changes)" if change.before == change.after else "(line endings changed)"
        body: Table | Text = Text(message, style="dim")
    else:
        old_text = _highlight(change.path, change.before) if change.kind != "created" else None
        new_text = _highlight(change.path, change.after)
        gutter = len(str(max(row[0] or 0 for row in shown)))
        body = Table.grid(expand=True, padding=0)
        body.add_column(width=gutter + 2, justify="right", no_wrap=True)
        body.add_column(width=3, justify="center", no_wrap=True)
        body.add_column(ratio=1)
        for row in shown:
            line_number, sign, content = row
            missing_newline = content.endswith(NO_EOL)
            content = content.removesuffix(NO_EOL)
            if sign == GAP:
                body.add_row("", Text(GAP, style="dim"), "")
                continue
            source = old_text if sign == "-" else new_text
            if source is not None and line_number is not None and line_number <= len(source):
                code = source[line_number - 1].copy()
            else:
                code = Text(content.expandtabs(4))
            if missing_newline:
                code.append(NO_EOL_NOTE, style="dim italic")
            code.overflow = "fold"
            body.add_row(
                Text(str(line_number), style=NUMBER_STYLES[sign]),
                Text(sign if sign != " " else "", style=SIGN_STYLES[sign]),
                code,
                style=ROW_STYLES[sign],
            )
    panel = Panel(
        body, title=title, title_align="left", subtitle=subtitle, subtitle_align="left",
        box=box.ROUNDED, border_style=BORDER, style=f"on {PANEL_BACKGROUND}", padding=(0, 0),
    )
    return panel, hidden
