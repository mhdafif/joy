"""Revert file changes that Joy recorded."""

from pathlib import Path

from joy.tools import _read_text, _save


def revert_change(root: Path, item: dict) -> bool:
    root = root.resolve()
    target = (root / item["path"]).resolve()
    if not target.is_relative_to(root):
        return False
    present = _read_text(target)
    if item["kind"] == "created":
        if present is None:
            return True
        if present != item["after"]:
            return False
        target.unlink()
        return True
    if present != item["after"]:
        return False
    _save(target, item["before"])
    return True
