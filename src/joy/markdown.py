"""Markdown styling for answers."""

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import CodeBlock, ListItem, Markdown
from rich.segment import Segment
from rich.syntax import Syntax
from rich.theme import Theme

from joy.theme import t

def markdown_theme() -> Theme:
    accent = t.accent
    return Theme({
        "markdown.code": t.code,
        "markdown.code_block": t.code,
        "markdown.strong": f"bold {accent}",
        "markdown.item.number": f"bold {accent}",
        "markdown.item.bullet": f"bold {accent}",
        "markdown.h1": f"bold {accent}",
        "markdown.h2": f"bold underline {accent}",
        "markdown.h3": f"bold {accent}",
        "markdown.h4": f"bold italic {accent}",
        "markdown.h5": f"italic {accent}",
        "markdown.h6": f"italic dim {accent}",
    })


class PlainCodeBlock(CodeBlock):
    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        yield Syntax(
            str(self.text).rstrip(), self.lexer_name, theme=self.theme, word_wrap=True,
            padding=(0, 1), background_color="default",
        )


class DottedListItem(ListItem):
    def render_number(self, console: Console, options: ConsoleOptions, number: int, last_number: int) -> RenderResult:
        number_width = len(str(last_number)) + 2
        lines = console.render_lines(
            self.elements, options.update(width=options.max_width - number_width), style=self.style,
        )
        style = console.get_style("markdown.item.number", default="none")
        numeral = Segment(f"{number}.".rjust(number_width - 1) + " ", style)
        padding = Segment(" " * number_width, style)
        for index, line in enumerate(lines):
            yield numeral if index == 0 else padding
            yield from line
            yield Segment("\n")


class JoyMarkdown(Markdown):
    elements = {
        **Markdown.elements,
        "fence": PlainCodeBlock,
        "code_block": PlainCodeBlock,
        "list_item_open": DottedListItem,
    }
