"""Decide which shell commands a saved approval covers."""

import re
import shlex
from pathlib import Path

from joy.tools import is_readonly_command

UNSAFE_MARKS = ("\n", "\r", "`", "$(", "<(", ">(")
OPERATORS = {";", "&&", "||", "|"}
HARMLESS = {"echo", "true", "false", "cd"}
INTERPRETERS = {"python", "python3", "node", "ruby", "perl", "php", "deno", "bun", "sh", "bash", "zsh"}
NEVER_PREFIX = {
    "rm", "rmdir", "sudo", "su", "chmod", "chown", "dd", "mkfs", "kill", "killall", "curl", "wget",
    "ssh", "scp", "eval", "exec", "xargs", "env", "nohup", "find",
} | INTERPRETERS - {"python", "python3"}
WORD = re.compile(r"[A-Za-z][\w-]*")
QUIET_REDIRECTS = (["2", ">&", "1"], ["2", ">", "/dev/null"])


def split_command(command: str) -> list[list[str]] | None:
    if any(mark in command for mark in UNSAFE_MARKS):
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    segments: list[list[str]] = [[]]
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if any(tokens[index:index + 3] == redirect for redirect in QUIET_REDIRECTS):
            index += 3
            continue
        if token in OPERATORS:
            segments.append([])
        elif token and all(char in ";&|<>()" for char in token):
            return None
        else:
            segments[-1].append(token)
        index += 1
    return None if any(not segment for segment in segments) else segments


def prefix_of(segment: list[str]) -> list[str] | None:
    program = segment[0]
    if program in NEVER_PREFIX:
        return None
    rest = segment[1:]
    if program in ("python", "python3") and rest[:1] == ["-m"] and len(rest) >= 2:
        return [program, "-m", rest[1]]
    prefix = [program]
    for token in rest[:2]:
        if not WORD.fullmatch(token):
            break
        prefix.append(token)
    return None if program in INTERPRETERS and len(prefix) == 1 else prefix


def needs_approval(root: Path, segment: list[str]) -> bool:
    return segment[0] not in HARMLESS and not is_readonly_command(root, shlex.join(segment))


def suggest_prefix(root: Path, command: str) -> list[str] | None:
    segments = split_command(command)
    if segments is None:
        return None
    risky = [segment for segment in segments if needs_approval(root, segment)]
    return prefix_of(risky[0]) if len(risky) == 1 else None


def is_allowed(root: Path, command: str, rules: list) -> bool:
    if command in rules:
        return True
    segments = split_command(command)
    if segments is None:
        return False
    prefixes = [rule["prefix"].split() for rule in rules if isinstance(rule, dict) and rule.get("prefix")]
    return all(
        not needs_approval(root, segment) or any(segment[:len(prefix)] == prefix for prefix in prefixes)
        for segment in segments
    )
