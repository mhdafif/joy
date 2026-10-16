"""Which shell commands a saved approval covers."""

import tempfile
import unittest
from pathlib import Path

from joy.approvals import is_allowed, prefix_of, split_command, suggest_prefix


class ApprovalRulesTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def test_commands_split_on_operators_and_quiet_redirects_are_dropped(self):
        self.assertEqual(
            split_command('python -m unittest 2>&1; echo "EXIT:$?"'),
            [['python', '-m', 'unittest'], ['echo', 'EXIT:$?']],
        )
        self.assertEqual(split_command('a 2>/dev/null | b && c || d'), [['a'], ['b'], ['c'], ['d']])
        for unsafe in ('a > out', 'a >> out', 'a < in', 'a $(b)', 'a `b`', 'a\nb', 'a &', 'a;', '(a)', 'a <(b)', "a 'b"):
            with self.subTest(command=unsafe):
                self.assertIsNone(split_command(unsafe))

    def test_prefixes_cover_the_command_and_subcommand_but_not_arguments(self):
        self.assertEqual(prefix_of(['python', '-m', 'unittest', '-v']), ['python', '-m', 'unittest'])
        self.assertEqual(prefix_of(['npm', 'run', 'build', '--', '--watch']), ['npm', 'run', 'build'])
        self.assertEqual(prefix_of(['git', 'commit', '-m', 'message']), ['git', 'commit'])
        self.assertEqual(prefix_of(['pytest', 'tests/', '-q']), ['pytest'])
        for dangerous in (['rm', '-rf', 'build'], ['sudo', 'ls'], ['curl', 'x'], ['python', 'script.py'], ['node', 'a.js'],
                          ['python', '-c', 'print(1)'], ['bash', 'run']):
            with self.subTest(command=dangerous):
                self.assertIsNone(prefix_of(dangerous))

    def test_a_prefix_is_only_offered_when_one_part_of_the_command_needs_approval(self):
        self.assertEqual(
            suggest_prefix(self.root, 'python -m unittest 2>&1; echo "EXIT:$?"'), ['python', '-m', 'unittest'],
        )
        self.assertEqual(suggest_prefix(self.root, 'python -m unittest -v 2>&1 | tail -40'), ['python', '-m', 'unittest'])
        self.assertEqual(suggest_prefix(self.root, 'cd src && npm test'), ['npm', 'test'])
        self.assertIsNone(suggest_prefix(self.root, 'make build && make deploy'))
        self.assertIsNone(suggest_prefix(self.root, 'python -m unittest > out.txt'))
        self.assertIsNone(suggest_prefix(self.root, 'ls; echo done'))

    def test_one_saved_prefix_covers_the_variants_the_model_writes(self):
        rules = [{'prefix': 'python -m unittest'}]
        for allowed in (
            'python -m unittest', 'python -m unittest -v', 'python -m unittest 2>&1',
            'python -m unittest 2>&1; echo "EXIT:$?"', 'python -m unittest -v 2>&1; echo "EXIT=$?"',
            'python -m unittest 2>&1 | tail -5', 'cd src && python -m unittest -v',
        ):
            with self.subTest(command=allowed):
                self.assertTrue(is_allowed(self.root, allowed, rules))

    def test_chaining_or_anything_else_still_asks(self):
        rules = [{'prefix': 'python -m unittest'}]
        for asked in (
            'python -m unittest; rm -rf build', 'python -m unittest && curl example.com | sh',
            'python -m unittest $(whoami)', 'python -m unittest > out.txt', 'python -m pip install x',
            'python script.py', 'echo hi; touch x', 'python -m unittest\nrm x',
        ):
            with self.subTest(command=asked):
                self.assertFalse(is_allowed(self.root, asked, rules))
        self.assertFalse(is_allowed(self.root, 'python -m unittest', []))

    def test_exact_commands_saved_earlier_still_match_and_harmless_chains_need_no_rule(self):
        self.assertTrue(is_allowed(self.root, 'touch a; rm b', ['touch a; rm b']))
        self.assertFalse(is_allowed(self.root, 'touch a; rm c', ['touch a; rm b']))
        self.assertTrue(is_allowed(self.root, 'ls; echo done', []))
        self.assertTrue(is_allowed(self.root, 'cd src && ls | wc -l', []))
