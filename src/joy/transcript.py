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
    def __init__(
        self, renderable: RenderableType, on_click: Callable[["Block"], None] | None = None,
        renderer: Callable[[str], RenderableType] | None = None,
        hit: Callable[["Block", int, int], bool] | None = None,
    ) -> None:
        self.renderable = renderable
        self.on_click = on_click
        self.renderer = renderer
        self.hit = hit
        self.state = "idle"
        self.width = 0
        self.lines: list[Line] = []

    def get(self, width: int) -> list[Line]:
        if width != self.width:
            self.lines = render_lines(self.renderer(self.state) if self.renderer else self.renderable, width)
            self.width = width
        return self.lines


class Transcript(UIControl):
    def __init__(self) -> None:
        self.blocks: list[Block] = []
        self.version = 0
        self.live_block: Block | None = None
        self.owners: list[Block | None] = []
        self.rows: list[int] = []
        self.visible: list[Block | None] = []
        self.visible_rows: list[int] = []
        self.hovered: Block | None = None
        self.scroll_back = 0
        self.height = 24
        self.total = 0
        self.joined_key: tuple[int, int] | None = None
        self.joined: list[Line] = []

    def add(
        self, renderable: RenderableType, on_click: Callable[[Block], None] | None = None,
        renderer: Callable[[str], RenderableType] | None = None,
        hit: Callable[["Block", int, int], bool] | None = None,
    ) -> Block:
        block = Block(renderable, on_click, renderer, hit)
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
        self.rows = []
        self.visible = []
        self.visible_rows = []
        self.hovered = None

    def set_hover(self, block: Block | None) -> None:
        if block is self.hovered:
            return
        previous, self.hovered = self.hovered, block
        if previous is not None and previous.state == "hover":
            previous.state = "idle"
            self.refresh(previous)
        if block is not None and block.state == "idle":
            block.state = "hover"
            self.refresh(block)

    def set_live(self, renderable: RenderableType | None) -> None:
        self.live_block = None if renderable is None else Block(renderable)
        self.version += 1

    def lines(self, width: int) -> list[Line]:
        key = (width, self.version)
        if key != self.joined_key:
            joined: list[Line] = []
            owners: list[Block | None] = []
            rows: list[int] = []
            for block in [*self.blocks, *([self.live_block] if self.live_block is not None else [])]:
                block_lines = block.get(width)
                joined.extend(block_lines)
                owners.extend([block] * len(block_lines))
                rows.extend(range(len(block_lines)))
            self.joined, self.owners, self.rows, self.joined_key = joined, owners, rows, key
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
        self.visible_rows = self.rows[start:end]
        return UIContent(
            get_line=lambda index: visible[index] if index < len(visible) else [],
            line_count=len(visible), show_cursor=False,
        )

    def target(self, mouse_event: MouseEvent) -> Block | None:
        row = mouse_event.position.y
        if not 0 <= row < len(self.visible):
            return None
        block = self.visible[row]
        if block is not None and block.hit is not None and not block.hit(
            block, self.visible_rows[row], mouse_event.position.x,
        ):
            return None
        return block

    def mouse_handler(self, mouse_event: MouseEvent):
        if mouse_event.event_type == MouseEventType.SCROLL_UP:
            self.scroll(WHEEL_STEP)
        elif mouse_event.event_type == MouseEventType.SCROLL_DOWN:
            self.scroll(-WHEEL_STEP)
        elif mouse_event.event_type == MouseEventType.MOUSE_MOVE:
            block = self.target(mouse_event)
            self.set_hover(block if block is not None and block.renderer is not None else None)
        elif mouse_event.event_type == MouseEventType.MOUSE_UP:
            block = self.target(mouse_event)
            if block is None or block.on_click is None:
                return NotImplemented
            block.on_click(block)
        else:
            return NotImplemented
        get_app().invalidate()
        return None
