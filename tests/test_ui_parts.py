import unittest
from rich.console import Console
from joy.cli import format_date, format_elapsed, format_tokens
from joy.steps import StepGroup, summarize
from joy.transcript import Transcript


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
