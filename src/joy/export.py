"""Turn a saved session into a Markdown document."""

from difflib import unified_diff
from time import localtime, strftime

from joy.sessions import Session

DIFF_LINES = 400


def _diff(item: dict) -> str:
    before = "" if item["kind"] == "created" else item["before"]
    lines = list(unified_diff(
        before.splitlines(), item["after"].splitlines(),
        fromfile="/dev/null" if item["kind"] == "created" else "a/" + item["path"], tofile="b/" + item["path"], lineterm="",
    ))
    if len(lines) > DIFF_LINES:
        lines = lines[:DIFF_LINES] + [f"... {len(lines) - DIFF_LINES} more lines"]
    return "\n".join(lines)


def to_markdown(session: Session) -> str:
    started = strftime("%Y-%m-%d %H:%M", localtime(session.created))
    out = [f"# {session.name}", "", f"- Folder: `{session.folder}`", f"- Started: {started}", ""]
    steps: list[dict] = []

    def flush() -> None:
        if steps:
            out.append("<details><summary>Steps</summary>\n")
            for step in steps:
                mark = "✗ " if step.get("status") == "failed" else ""
                out.append(f"- {mark}`{step['name']}` {step.get('detail', '')}".rstrip())
            out.append("\n</details>\n")
            steps.clear()

    for event in session.events:
        kind = event["t"]
        if kind == "tool":
            steps.append(event)
            continue
        flush()
        if kind == "user":
            out += ["## You", "", event["text"], ""]
            if event.get("attached"):
                out += ["_Attached: " + ", ".join(event["attached"]) + "_", ""]
        elif kind in ("text", "answer"):
            out += ["## Joy", "", event["text"].strip(), ""]
        elif kind == "changes":
            for item in event["items"]:
                label = "Created" if item["kind"] == "created" else "Modified"
                out += [f"**{label} `{item['path']}`**", "", "```diff", _diff(item), "```", ""]
        elif kind == "footer":
            details = [event["model"], f"{int(event['elapsed'])}s"]
            if event.get("tokens"):
                details.append(f"{event['tokens']} tokens")
            out += ["_" + " | ".join(details) + "_", ""]
        elif kind == "compact":
            out += ["_Conversation compacted._", "", event.get("summary", ""), ""]
        elif kind == "cancelled":
            out += ["_Response cancelled._", ""]
        elif kind == "error":
            out += ["> " + event["text"], ""]
    flush()
    return "\n".join(out).rstrip() + "\n"
