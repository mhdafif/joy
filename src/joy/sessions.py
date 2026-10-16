"""Save and restore conversations so they can be continued later."""

import json
import secrets
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from joy.settings import joy_home

NAME_LIMIT = 80


@dataclass
class Session:
    id: str
    folder: str
    name: str
    created: float
    updated: float
    messages: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)


def sessions_dir() -> Path:
    return joy_home() / "sessions"


def session_name(message: str) -> str:
    text = " ".join(message.split())
    return text if len(text) <= NAME_LIMIT else text[:NAME_LIMIT - 1] + "…"


def new_session(folder: str, first_message: str) -> Session:
    now = time.time()
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    return Session(f"{stamp}-{secrets.token_hex(3)}", folder, session_name(first_message) or "Untitled", now, now)


def save_session(session: Session) -> None:
    directory = sessions_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False, encoding="utf-8") as file:
            temporary = Path(file.name)
            json.dump(asdict(session), file, ensure_ascii=False)
        temporary.chmod(0o600)
        temporary.replace(directory / f"{session.id}.json")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def list_sessions(folder: str) -> list[Session]:
    found: list[Session] = []
    for path in sessions_dir().glob("*.json"):
        try:
            session = Session(**json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            continue
        if session.folder == folder:
            found.append(session)
    return sorted(found, key=lambda session: session.updated, reverse=True)


def latest_session(folder: str) -> Session | None:
    found = list_sessions(folder)
    return found[0] if found else None


def delete_session(session: Session) -> None:
    (sessions_dir() / f"{session.id}.json").unlink(missing_ok=True)
