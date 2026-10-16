"""Diff rows, newline handling, and panel rendering."""

import random
import unittest

from rich.console import Console

from joy.diffview import GAP, _opcodes, _rows, merge_changes, render_change
from joy.tools import Change


def render_text(change, **options):
    panel, hidden = render_change(change, **options)
    console = Console(width=80, force_terminal=False, color_system=None)
    with console.capture() as capture:
        console.print(panel)
    return capture.get(), hidden


def apply(old, new, ops):
    result = []
    for tag, i1, i2, j1, j2 in ops:
        result.extend(old[i1:i2] if tag == 'equal' else new[j1:j2])
    return result


class DiffTest(unittest.TestCase):
    def test_opcodes_rebuild_the_new_text_for_random_inputs(self):
        generator = random.Random(7)
        for _ in range(200):
            alphabet = ['a', 'b', 'c', 'd', 'e']
            old = [generator.choice(alphabet) for _ in range(generator.randint(0, 25))]
            new = list(old)
            for _ in range(generator.randint(0, 6)):
                action = generator.choice(['insert', 'delete', 'replace'])
                position = generator.randint(0, len(new))
                if action == 'insert' or not new:
                    new.insert(position, generator.choice(alphabet))
                elif action == 'delete':
                    del new[min(position, len(new) - 1)]
                else:
                    new[min(position, len(new) - 1)] = generator.choice(alphabet)
            with self.subTest(old=old, new=new):
                self.assertEqual(apply(old, new, _opcodes(old, new)), new)

    def test_final_newline_changes_are_visible(self):
        rows = _rows(Change('f.txt', 'modified', 'a\nb', 'a\nb\n'))
        signs = [(sign, content.rstrip('\x00')) for _, sign, content in rows if sign in '+-']
        self.assertEqual(signs, [('-', 'b'), ('+', 'b')])
        text, _ = render_text(Change('f.txt', 'modified', 'a\nb', 'a\nb\n'))
        self.assertIn('no newline at end of file', text)

    def test_context_gap_and_hidden_count(self):
        before = ''.join(f'line {n}\n' for n in range(1, 41))
        after = before.replace('line 5\n', 'CHANGED 5\n').replace('line 35\n', 'CHANGED 35\n')
        rows = _rows(Change('f.txt', 'modified', before, after))
        self.assertIn(GAP, [sign for _, sign, _ in rows])
        self.assertEqual(sum(1 for _, sign, _ in rows if sign == '+'), 2)
        text, hidden = render_text(Change('big.txt', 'created', '', before), limit=5)
        self.assertEqual(hidden, 35)
        self.assertIn('35 more lines · click to expand', text)

    def test_empty_and_unchanged_messages(self):
        self.assertIn('(empty file)', render_text(Change('e.txt', 'created', '', ''))[0])
        self.assertIn('(no changes)', render_text(Change('e.txt', 'modified', 'a\n', 'a\n'))[0])
        self.assertIn('(line endings changed)', render_text(Change('e.txt', 'modified', 'a\r\nb\r\n', 'a\nb\n'))[0])

    def test_changes_to_the_same_file_merge_into_one(self):
        merged = merge_changes([
            Change('a.txt', 'created', '', 'one'),
            Change('b.txt', 'modified', 'x', 'y'),
            Change('a.txt', 'modified', 'one', 'two'),
        ])
        self.assertEqual([(c.path, c.kind, c.before, c.after) for c in merged],
                         [('a.txt', 'created', '', 'two'), ('b.txt', 'modified', 'x', 'y')])

    def test_repetitive_files_diff_quickly(self):
        old = ['same'] * 6000
        new = list(old)
        new[4000] = 'different'
        self.assertEqual(apply(old, new, _opcodes(old, new)), new)
