"""Saved API connections and the selected model."""

import os
from dataclasses import dataclass

from joy.settings import load_settings, save_settings

DEFAULT_NAME = "Default"
RECENT_LIMIT = 5


@dataclass(frozen=True)
class Connection:
    name: str
    base_url: str = ""
    api_key: str = ""

    def client_options(self) -> dict[str, str]:
        options: dict[str, str] = {}
        if self.base_url:
            options["base_url"] = self.base_url
        if self.api_key:
            options["api_key"] = self.api_key
        return options

    def describe(self) -> str:
        if self.base_url:
            return self.base_url
        return os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"


def load_connections() -> list[Connection]:
    saved = []
    for item in load_settings().get("connections", []):
        if isinstance(item, dict) and all(item.get(key) for key in ("name", "base_url", "api_key")):
            saved.append(Connection(str(item["name"]), str(item["base_url"]), str(item["api_key"])))
    return [Connection(DEFAULT_NAME), *saved]


def save_connection(connection: Connection) -> bool:
    values = load_settings()
    items = [item for item in values.get("connections", []) if isinstance(item, dict)]
    entry = {"name": connection.name, "base_url": connection.base_url, "api_key": connection.api_key}
    for index, item in enumerate(items):
        if str(item.get("name", "")).lower() == connection.name.lower():
            items[index] = entry
            replaced = True
            break
    else:
        items.append(entry)
        replaced = False
    values["connections"] = items
    save_settings(values)
    return replaced


def load_selection(connections: list[Connection], default_model: str) -> tuple[Connection, str]:
    values = load_settings()
    selection = values.get("selection")
    if isinstance(selection, dict):
        name, model = selection.get("connection"), selection.get("model")
    elif values.get("model"):
        name, model = DEFAULT_NAME, values["model"]
    else:
        name, model = DEFAULT_NAME, default_model
    for connection in connections:
        if connection.name == name:
            return connection, str(model or default_model)
    return connections[0], default_model


def load_recent() -> list[tuple[str, str]]:
    recent = []
    for item in load_settings().get("recent", []):
        if isinstance(item, dict) and item.get("connection") and item.get("model"):
            recent.append((str(item["connection"]), str(item["model"])))
    return recent


def save_selection(connection: Connection, model: str) -> None:
    values = load_settings()
    values["selection"] = {"connection": connection.name, "model": model}
    values.pop("model", None)
    recent = [pair for pair in load_recent() if pair != (connection.name, model)]
    values["recent"] = [
        {"connection": name, "model": chosen}
        for name, chosen in [(connection.name, model), *recent][:RECENT_LIMIT]
    ]
    save_settings(values)
