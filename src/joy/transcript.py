"""Scrollable transcript for the full-screen interface, rendered from Rich objects."""

import re
from collections.abc import Callable
from io import StringIO

from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import ANSI, StyleAndTextTuples, fragment_list_to_text, to_formatted_text
from prompt_toolkit.formatted_text.utils import split_lines
from prompt_toolkit.layout.controls import UIContent, UIControl
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from rich.console import Console, RenderableType

from joy.markdown import markdown_theme

LINK = re.compile(r"\x1b\]8;[^\x1b]*\x1b\\")
WHEEL_STEP = 3
MIN_WIDTH = 20

Line = StyleAndTextTuples


def render_lines(renderable: RenderableType, width: int) -> list[Line]:
    console = Console(
        file=StringIO(), force_terminal=True, color_system="truecolor", no_color=False,
        width=max(width, MIN_WIDTH), legacy_windows=False, theme=markdown_theme(),
    )
    console.print(renderable)
    text = LINK.sub("", console.file.getvalue())
    lines = list(split_lines(to_formatted_text(ANSI(text))))
    if lines and not fragment_list_to_text(lines[-1]):
        lines.pop()
    return lines


class Block:
    def __init__(self, renderable: RenderableType, on_click: Callable[["Block"], None] | None = None) -> None:
        self.renderable = renderable
        self.on_click = on_click
        self.width = 0
        self.lines: list[Line] = []

    def get(self, width: int) -> list[Line]:
        if width != self.width:
            self.lines = render_lines(self.renderable, width)
            self.width = width
        return self.lines


class Transcript(UIControl):
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self.version = 0
        self.live_block: Block | None = None
        self.owners: list[Block | None] = []
        self.visible: list[Block | None] = []
        self.scroll_back = 0
        self.height = 24
        self.total = 0
        self.joined_key: tuple[int, int] | None = None
        self.joined: list[Line] = []

    def add(self, renderable: RenderableType, on_click: Callable[[Block], None] | None = None) -> Block:
        block = Block(renderable, on_click)
        self.blocks.append(block)
        self.version += 1
        return block

    def refresh(self, block: Block) -> None:
        block.width = 0
        self.version += 1

    def clear(self) -> None:
        self.blocks.clear()
        self.set_live(None)
        self.scroll_back = 0
        self.total = 0
        self.joined_key = None
        self.joined = []
        self.owners = []
        self.visible = []

    def set_live(self, renderable: RenderableType | None) -> None:
        self.live_block = None if renderable is None else Block(renderable)
        self.version += 1

    def lines(self, width: int) -> list[Line]:
        key = (width, self.version)
        if key != self.joined_key:
            joined: list[Line] = []
            owners: list[Block | None] = []
            for block in [*self.blocks, *([self.live_block] if self.live_block is not None else [])]:
                block_lines = block.get(width)
                joined.extend(block_lines)
                owners.extend([block] * len(block_lines))
            self.joined, self.owners, self.joined_key = joined, owners, key
        return self.joined

    def plain(self, width: int = 80) -> str:
        return "\n".join(fragment_list_to_text(line) for line in self.lines(width))

    def scroll(self, lines: int) -> None:
        self.scroll_back = max(0, self.scroll_back + lines)

    def page(self, direction: int) -> None:
        self.scroll(direction * max(1, self.height - 2))

    def jump_to_end(self) -> None:
        self.scroll_back = 0

    def is_focusable(self) -> bool:
        return False

    def create_content(self, width: int, height: int) -> UIContent:
        lines = self.lines(width)
        total = len(lines)
        if self.scroll_back and self.total:
            self.scroll_back += total - self.total
        self.total = total
        self.height = height
        self.scroll_back = max(0, min(self.scroll_back, total - height))
        end = total - self.scroll_back
        start = max(0, end - height)
        visible = lines[start:end]
        self.visible = self.owners[start:end]
        return UIContent(
            get_line=lambda index: visible[index] if index < len(visible) else [],
            line_count=len(visible), show_cursor=False,
        )

    def mouse_handler(self, mouse_event: MouseEvent):
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self.scroll(WHEEL_STEP)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self.scroll(-WHEEL_STEP)
        elif mouse_event.event_type == MouseEventType.MOUSE_UP:
            row = mouse_event.position.y
            block = self.visible[row] if 0 <= row < len(self.visible) else None
            if block is None or block.on_click is None:
                return NotImplemented
            block.on_click(block)
        else:
            return NotImplemented
        get_app().invalidate()
        return None
