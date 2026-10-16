"""Render file changes as syntax-highlighted diff panels for the terminal."""

from difflib import SequenceMatcher

from rich import box
from rich.panel import Panel
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Span, Text

from joy.theme import t
from joy.tools import Change

COLLAPSED_LINES = 20
MAX_EDITS = 2000
NO_EOL = "\x00"
NO_EOL_NOTE = "  ⏎ no newline at end of file"
CONTEXT_LINES = 3
HIGHLIGHT_LIMIT = 200_000
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


def _myers(old: list[str], new: list[str]) -> list[tuple[str, int, int, int, int]] | None:
    n, m = len(old), len(new)
    limit = min(n + m, MAX_EDITS)
    offset = limit + 1
    v = [0] * (2 * limit + 3)
    trace: list[list[int]] = []
    for d in range(limit + 1):
        trace.append(v[offset - d - 1:offset + d + 2])
        for k in range(-d, d + 1, 2):
            if k == -d or (k != d and v[offset + k - 1] < v[offset + k + 1]):
                x = v[offset + k + 1]
            else:
                x = v[offset + k - 1] + 1
            y = x - k
            while x < n and y < m and old[x] == new[y]:
                x += 1
                y += 1
            v[offset + k] = x
            if x >= n and y >= m:
                return _myers_ops(trace, n, m)
    return None


def _myers_ops(trace: list[list[int]], n: int, m: int) -> list[tuple[str, int, int, int, int]]:
    steps: list[str] = []
    x, y = n, m
    for d in range(len(trace) - 1, -1, -1):
        snapshot = trace[d]
        k = x - y
        if k == -d or (k != d and snapshot[k - 1 + d + 1] < snapshot[k + 1 + d + 1]):
            previous_k = k + 1
        else:
            previous_k = k - 1
        previous_x = snapshot[previous_k + d + 1]
        previous_y = previous_x - previous_k
        while x > previous_x and y > previous_y:
            steps.append("e")
            x -= 1
            y -= 1
        if d > 0:
            steps.append("d" if x > previous_x else "i")
        x, y = previous_x, previous_y
    steps.reverse()
    ops: list[tuple[str, int, int, int, int]] = []
    i = j = 0
    position = 0
    while position < len(steps):
        end = position
        equal = steps[position] == "e"
        while end < len(steps) and (steps[end] == "e") == equal:
            end += 1
        run = steps[position:end]
        if equal:
            ops.append(("equal", i, i + len(run), j, j + len(run)))
            i += len(run)
            j += len(run)
        else:
            deleted, inserted = run.count("d"), run.count("i")
            tag = "replace" if deleted and inserted else "delete" if deleted else "insert"
            ops.append((tag, i, i + deleted, j, j + inserted))
            i += deleted
            j += inserted
        position = end
    return ops


def _opcodes(old: list[str], new: list[str]) -> list[tuple[str, int, int, int, int]]:
    shortest = min(len(old), len(new))
    start = 0
    while start < shortest and old[start] == new[start]:
        start += 1
    end = 0
    while end < shortest - start and old[-1 - end] == new[-1 - end]:
        end += 1
    old_end, new_end = len(old) - end, len(new) - end
    ops: list[tuple[str, int, int, int, int]] = []
    if start:
        ops.append(("equal", 0, start, 0, start))
    middle_old, middle_new = old[start:old_end], new[start:new_end]
    if middle_old or middle_new:
        if not middle_old:
            ops.append(("insert", start, start, start, new_end))
        elif not middle_new:
            ops.append(("delete", start, old_end, start, start))
        else:
            found = _myers(middle_old, middle_new)
            if found is None:
                matcher = SequenceMatcher(None, middle_old, middle_new, autojunk=True)
                found = matcher.get_opcodes()
            ops.extend((tag, i1 + start, i2 + start, j1 + start, j2 + start)
                       for tag, i1, i2, j1, j2 in found)
    if end:
        ops.append(("equal", old_end, len(old), new_end, len(new)))
    return ops


def _grouped(ops: list[tuple[str, int, int, int, int]]) -> list[list[tuple[str, int, int, int, int]]]:
    if not any(tag != "equal" for tag, *_ in ops):
        return []
    ops = list(ops)
    tag, i1, i2, j1, j2 = ops[0]
    if tag == "equal":
        ops[0] = (tag, max(i1, i2 - CONTEXT_LINES), i2, max(j1, j2 - CONTEXT_LINES), j2)
    tag, i1, i2, j1, j2 = ops[-1]
    if tag == "equal":
        ops[-1] = (tag, i1, min(i2, i1 + CONTEXT_LINES), j1, min(j2, j1 + CONTEXT_LINES))
    groups: list[list[tuple[str, int, int, int, int]]] = []
    group: list[tuple[str, int, int, int, int]] = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal" and i2 - i1 > 2 * CONTEXT_LINES:
            group.append((tag, i1, min(i2, i1 + CONTEXT_LINES), j1, min(j2, j1 + CONTEXT_LINES)))
            groups.append(group)
            group = []
            i1, j1 = max(i1, i2 - CONTEXT_LINES), max(j1, j2 - CONTEXT_LINES)
        group.append((tag, i1, i2, j1, j2))
    if group:
        groups.append(group)
    return groups


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
    for group in _grouped(_opcodes(old, new)):
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
    row_styles = {"+": t.add_row, "-": t.remove_row, " ": ""}
    sign_styles = {"+": t.add_sign, "-": t.remove_sign, " ": ""}
    number_styles = {"+": t.gutter, "-": t.gutter, " ": t.faint}
    rows = _rows(change)
    added = sum(1 for _, sign, _ in rows if sign == "+")
    removed = sum(1 for _, sign, _ in rows if sign == "-")
    title = Text.assemble(
        (f"{LABELS[change.kind]} ", "bold"), (change.path, t.info),
        (f"  +{added}", t.success), *([(f" −{removed}", t.danger)] if removed else []),
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
                Text(str(line_number), style=number_styles[sign]),
                Text(sign if sign != " " else "", style=sign_styles[sign]),
                code,
                style=row_styles[sign],
            )
    panel = Panel(
        body, title=title, title_align="left", subtitle=subtitle, subtitle_align="left",
        box=box.ROUNDED, border_style=t.border, style=t.panel, padding=(0, 0),
    )
    return panel, hidden
