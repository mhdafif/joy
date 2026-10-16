"""Project instructions and skills discovery."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from joy.instructions import find_instruction_files, load_instructions
from joy.skills import discover, load_body


class ContextCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.home.cleanup)
        environment = patch.dict(os.environ, {'JOY_HOME': self.home.name})
        environment.start()
        self.addCleanup(environment.stop)
        self.root = Path(self.directory.name).resolve()


class InstructionsTest(ContextCase):
    def test_nothing_is_loaded_when_there_are_no_files(self):
        self.assertEqual(load_instructions(self.root), ('', []))

    def test_agents_file_wins_over_claude_file_in_the_same_folder(self):
        (self.root / 'AGENTS.md').write_text('use tabs')
        (self.root / 'CLAUDE.md').write_text('use spaces')
        text, files = load_instructions(self.root)
        self.assertEqual([f.name for f in files], ['AGENTS.md'])
        self.assertIn('use tabs', text)
        self.assertNotIn('use spaces', text)

    def test_parent_folders_up_to_the_git_root_and_global_file_are_included_in_order(self):
        (self.root / '.git').mkdir()
        (self.root / 'AGENTS.md').write_text('repo rules')
        inner = self.root / 'pkg'
        inner.mkdir()
        (inner / 'CLAUDE.md').write_text('package rules')
        (Path(self.home.name) / 'AGENTS.md').write_text('global rules')
        text, files = load_instructions(inner)
        self.assertEqual([f.parent.name for f in files], [Path(self.home.name).name, self.root.name, 'pkg'])
        self.assertLess(text.index('global rules'), text.index('repo rules'))
        self.assertLess(text.index('repo rules'), text.index('package rules'))

    def test_without_a_git_root_only_the_current_folder_counts(self):
        (self.root / 'AGENTS.md').write_text('outer')
        inner = self.root / 'pkg'
        inner.mkdir()
        self.assertEqual(find_instruction_files(inner), [])

    def test_very_large_files_are_cut(self):
        (self.root / 'AGENTS.md').write_text('x' * 50_000)
        text, _ = load_instructions(self.root)
        self.assertLess(len(text), 21_000)


class SkillsTest(ContextCase):
    def write_skill(self, directory, name, description, body='Do the thing.'):
        folder = directory / name
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: {description}\n---\n{body}\n')

    def test_project_skills_override_user_skills_and_bodies_load_without_the_header(self):
        self.write_skill(self.root / '.claude' / 'skills', 'commit', 'Commit things')
        self.write_skill(self.root / '.joy' / 'skills', 'commit', 'Joy commit', 'JOY BODY')
        self.write_skill(Path(self.home.name) / 'skills', 'review', 'Review code')
        found = discover(self.root)
        self.assertEqual(sorted(found), ['commit', 'review'])
        self.assertEqual(found['commit'].description, 'Joy commit')
        body = load_body(found['commit'])
        self.assertIn('JOY BODY', body)
        self.assertNotIn('description:', body)

    def test_folder_name_and_first_line_are_used_without_a_header(self):
        folder = self.root / '.claude' / 'skills' / 'plain'
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text('\nFirst line describes it.\nMore.\n')
        skill = discover(self.root)['plain']
        self.assertEqual(skill.description, 'First line describes it.')

    def test_missing_folders_are_fine(self):
        self.assertEqual(discover(self.root), {})
