"""Finding and attaching files mentioned with @."""

import tempfile
import unittest
from pathlib import Path

from joy.mentions import active_mention, expand, references, search, workspace_paths


class MentionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        (self.root / 'src').mkdir()
        (self.root / 'calc.py').write_text('def add(a, b):\n    return a + b\n')
        (self.root / 'test_calc.py').write_text('import calc\n')
        (self.root / 'src' / 'util.py').write_text('X = 1\n')
        (self.root / 'blob.bin').write_bytes(b'\x00\x01\x02')
        (self.root / 'node_modules').mkdir()
        (self.root / 'node_modules' / 'skip.js').write_text('x')

    def test_active_mention_needs_a_token_that_starts_with_at(self):
        self.assertEqual(active_mention('explain @ca', 11), (8, 'ca'))
        self.assertEqual(active_mention('@', 1), (0, ''))
        self.assertIsNone(active_mention('mail me@x.com', 13))
        self.assertIsNone(active_mention('plain text', 10))
        self.assertIsNone(active_mention('@done ', 6))

    def test_references_mark_skills_and_existing_paths_only(self):
        message = 'run @review on @calc.py, @src/ and @nothing.py then @review.'
        self.assertEqual(
            [(message[a:b], kind) for a, b, kind in references(self.root, message, {'review'})],
            [('@review', 'skill'), ('@calc.py', 'file'), ('@src/', 'file'), ('@review', 'skill')],
        )
        self.assertEqual(references(self.root, 'mail me@calc.py', set()), [])

    def test_search_ranks_name_matches_first_and_handles_no_match(self):
        paths = workspace_paths(self.root)
        self.assertIn('calc.py', paths)
        self.assertIn('src/', paths)
        self.assertNotIn('node_modules/skip.js', paths)
        results = search(paths, 'calc')
        self.assertEqual(results[:2], ['calc.py', 'test_calc.py'])
        self.assertEqual(search(paths, 'zzzz'), [])
        self.assertIn('src/util.py', search(paths, 'src/'))

    def test_expand_attaches_files_and_folders(self):
        content, attached = expand(self.root, 'explain @calc.py and @src/')
        self.assertTrue(content.startswith('explain @calc.py and @src/'))
        self.assertIn('<file path="calc.py">\ndef add(a, b):', content)
        self.assertIn('<directory path="src/">\nutil.py', content)
        self.assertEqual(attached, ['calc.py (2 lines)', 'src/ (1 entries)'])

    def test_expand_skips_binary_missing_outside_and_repeated_mentions(self):
        content, attached = expand(self.root, 'see @blob.bin @missing.txt @../outside mail me@x.com @calc.py, @calc.py')
        self.assertEqual(attached, ['blob.bin (not attached: binary or too large)', 'calc.py (2 lines)'])
        self.assertEqual(content.count('<file path="calc.py">'), 1)
        self.assertNotIn('<file path="blob.bin">', content)
        plain, none = expand(self.root, 'nothing to attach here')
        self.assertEqual((plain, none), ('nothing to attach here', []))
