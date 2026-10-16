import re
import unittest
from pathlib import Path
from prompt_toolkit.formatted_text import fragment_list_to_text
from rich.console import Console
from joy import theme
from joy.cli import format_date, format_elapsed, format_tokens
from joy.markdown import JoyMarkdown
from joy.steps import StepGroup, summarize
from joy.transcript import Transcript, render_lines
"""Steps, theme, markdown, transcript interaction, and clipboard helpers."""


def render_plain(renderable, width=60):
    console = Console(width=width, force_terminal=False, color_system=None)
    with console.capture() as capture:
        console.print(renderable)
    return capture.get()


class StepsTest(unittest.TestCase):
    def test_summaries_are_short_sentences(self):
        read = {'name': 'read', 'detail': 'a.py'}
        self.assertEqual(summarize([read]), 'Read a.py')
        self.assertEqual(summarize([read, {'name': 'read', 'detail': 'b.py'}]), 'Read 2 files')
        steps = [read, {'name': 'edit', 'detail': 'a.py'}, {'name': 'bash', 'detail': 'pytest'}, {'name': 'bash', 'detail': 'ls'}]
        self.assertEqual(summarize(steps), 'Read a.py, edited a.py and ran 2 commands')
        self.assertEqual(summarize([{'name': 'mystery'}, {'name': 'other'}]), 'Used 2 other tools')

    def test_failed_steps_are_counted_and_explained(self):
        group = StepGroup(True, [
            {'name': 'bash', 'detail': 'false', 'status': 'failed', 'error': 'declined'},
            {'name': 'read', 'detail': 'a.py'},
        ])
        text = render_plain(group)
        self.assertIn('1 failed', text)
        self.assertIn('✗ false — declined', text)


class ThemeTest(unittest.TestCase):
    def tearDown(self):
        theme.use(theme.DEFAULT_PALETTE)

    def test_every_palette_defines_every_color_as_hex(self):
        colors = [name for name in theme.Palette.__dataclass_fields__ if name not in ('key', 'name', 'description')]
        self.assertGreaterEqual(len(theme.PALETTES), 5)
        for key, palette in theme.PALETTES.items():
            self.assertEqual(palette.key, key)
            for color in colors:
                with self.subTest(palette=key, color=color):
                    self.assertRegex(getattr(palette, color), r'^#[0-9a-f]{6}$')

    def test_main_text_and_accent_labels_are_readable_in_every_palette(self):
        def luminance(value):
            channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
            channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
            return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

        def contrast(a, b):
            high, low = sorted((luminance(a), luminance(b)), reverse=True)
            return (high + 0.05) / (low + 0.05)

        for palette in theme.PALETTES.values():
            with self.subTest(palette=palette.key):
                self.assertGreaterEqual(contrast(palette.text, palette.surface), 4.5)
                self.assertGreaterEqual(contrast(palette.on_accent, palette.accent), 4.5)
                self.assertGreaterEqual(contrast(palette.on_accent, palette.secondary), 4.5)

    def test_switching_palettes_changes_the_tokens_everyone_reads(self):
        self.assertTrue(theme.use('ember'))
        self.assertEqual(theme.t.accent, theme.PALETTES['ember'].accent)
        self.assertEqual(theme.t.selected, f'bg:{theme.PALETTES["ember"].accent} {theme.PALETTES["ember"].on_accent}')
        self.assertTrue(theme.use('moss'))
        self.assertEqual(theme.t.accent, theme.PALETTES['moss'].accent)
        self.assertFalse(theme.use('does-not-exist'))
        self.assertFalse(theme.use(None))
        self.assertEqual(theme.active().key, 'moss')

    def test_colors_live_only_in_the_theme_module(self):
        for file in Path(theme.__file__).parent.glob('*.py'):
            if file.name == 'theme.py':
                continue
            with self.subTest(file=file.name):
                self.assertIsNone(re.search(r'#[0-9a-fA-F]{6}', file.read_text()))


class MarkdownTest(unittest.TestCase):
    def tearDown(self):
        theme.use(theme.DEFAULT_PALETTE)

    def test_lists_are_numbered_with_dots_and_inline_code_has_no_background(self):
        theme.use('ember')
        lines = render_lines(JoyMarkdown('1. First `a`\n2. **Second** step\n\n```python\nx = 1\n```\n'), 50)
        plain = [fragment_list_to_text(line).rstrip() for line in lines]
        self.assertIn('1. First a', plain)
        self.assertIn('2. Second step', plain)
        code_styles = [style for line in lines for style, text, *_ in line if text == 'a']
        self.assertTrue(code_styles)
        self.assertIn(theme.PALETTES['ember'].code, code_styles[0])
        self.assertNotIn('bg:#', code_styles[0])
        bold_styles = [style for line in lines for style, text, *_ in line if text == 'S']
        self.assertIn(theme.PALETTES['ember'].accent, bold_styles[0])
        block_styles = ' '.join(style for line in lines for style, text, *_ in line if text == 'x')
        self.assertNotIn('bg:#', block_styles)


class TranscriptInteractionTest(unittest.TestCase):




    def test_refreshing_a_block_redraws_it_and_live_content_is_shown_last(self):
        transcript = Transcript()
        block = transcript.add('first')
        block.renderable = 'changed'
        transcript.refresh(block)
        transcript.set_live('live text')
        text = transcript.plain(40)
        self.assertEqual(text.splitlines(), ['changed', 'live text'])
        transcript.set_live(None)
        self.assertEqual(transcript.plain(40), 'changed')


class SmallHelpersTest(unittest.TestCase):
    def test_formatting(self):
        self.assertEqual((format_elapsed(5), format_elapsed(65), format_elapsed(600)), ('5s', '1m 05s', '10m 00s'))
        self.assertEqual((format_tokens(842), format_tokens(12_345)), ('842 tokens', '12.3k tokens'))
        self.assertRegex(format_date(1_700_000_000), r'^\w{3} \d{2}( \d{4}|, \d{2}:\d{2})$')
