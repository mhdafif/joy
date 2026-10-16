import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from joy import sessions
from joy.connections import (
    DEFAULT_NAME, Connection, load_connections, load_recent, load_selection, save_connection, save_selection,
)
from joy.export import to_markdown
from joy.settings import load_settings, save_settings
from joy.undo import revert_change
"""Sessions, settings, connections, undo, and export, against a temporary home folder."""


class HomeCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        environment = patch.dict(os.environ, {'JOY_HOME': self.home.name})
        environment.start()
        self.addCleanup(environment.stop)


class SettingsTest(HomeCase):
    def test_settings_round_trip_and_survive_bad_files(self):
        self.assertEqual(load_settings(), {})
        save_settings({'theme': 'moss'})
        self.assertEqual(load_settings(), {'theme': 'moss'})
        (Path(self.home.name) / 'settings.json').write_text('not json')
        self.assertEqual(load_settings(), {})
        (Path(self.home.name) / 'settings.json').write_text('[1, 2]')
        self.assertEqual(load_settings(), {})
        self.assertEqual(oct((Path(self.home.name)).stat().st_mode & 0o777), '0o700')


class SessionTest(HomeCase):
    def test_names_are_a_clean_first_line_and_limited(self):
        self.assertEqual(sessions.session_name('  fix   the\nbug  '), 'fix the bug')
        self.assertEqual(len(sessions.session_name('x' * 200)), 80)

    def test_save_list_latest_and_delete(self):
        first = sessions.new_session('/work/a', 'first task')
        second = sessions.new_session('/work/a', 'second task')
        other = sessions.new_session('/work/b', 'elsewhere')
        second.updated = first.updated + 10
        for session in (first, second, other):
            sessions.save_session(session)
        self.assertEqual([s.name for s in sessions.list_sessions('/work/a')], ['second task', 'first task'])
        self.assertEqual(sessions.latest_session('/work/a').name, 'second task')
        self.assertIsNone(sessions.latest_session('/work/none'))
        sessions.delete_session(second)
        self.assertEqual([s.name for s in sessions.list_sessions('/work/a')], ['first task'])
        path = Path(self.home.name) / 'sessions' / f'{first.id}.json'
        self.assertEqual(oct(path.stat().st_mode & 0o777), '0o600')
        path.write_text('{broken')
        self.assertEqual(sessions.list_sessions('/work/a'), [])


class ConnectionTest(HomeCase):
    def test_default_connection_always_exists_and_saved_ones_follow(self):
        self.assertEqual([c.name for c in load_connections()], [DEFAULT_NAME])
        self.assertFalse(save_connection(Connection('9router', 'http://x/v1', 'sk-1')))
        self.assertTrue(save_connection(Connection('9ROUTER', 'http://y/v1', 'sk-2')))
        saved = load_connections()
        self.assertEqual([(c.name, c.base_url, c.api_key) for c in saved[1:]], [('9ROUTER', 'http://y/v1', 'sk-2')])
        self.assertEqual(saved[1].client_options(), {'base_url': 'http://y/v1', 'api_key': 'sk-2'})
        self.assertEqual(saved[0].client_options(), {})

    def test_selection_recents_and_legacy_model_setting(self):
        connections = [Connection(DEFAULT_NAME), Connection('r', 'http://x/v1', 'k')]
        self.assertEqual(load_selection(connections, 'dflt'), (connections[0], 'dflt'))
        save_settings({'model': 'old-model'})
        self.assertEqual(load_selection(connections, 'dflt'), (connections[0], 'old-model'))
        save_selection(connections[1], 'm1')
        self.assertEqual(load_selection(connections, 'dflt'), (connections[1], 'm1'))
        self.assertNotIn('model', load_settings())
        for number in range(7):
            save_selection(connections[0], f'n{number}')
        save_selection(connections[1], 'm1')
        self.assertEqual(load_recent()[0], ('r', 'm1'))
        self.assertEqual(len(load_recent()), 5)
        self.assertEqual(load_selection([Connection(DEFAULT_NAME)], 'dflt'), (Connection(DEFAULT_NAME), 'dflt'))


class UndoTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_modified_files_are_restored_only_if_untouched_since(self):
        file = self.root / 'a.txt'
        file.write_text('new\n')
        item = {'path': 'a.txt', 'kind': 'modified', 'before': 'old\n', 'after': 'new\n'}
        file.write_text('edited by the user\n')
        self.assertFalse(revert_change(self.root, item))
        self.assertEqual(file.read_text(), 'edited by the user\n')
        file.write_text('new\n')
        self.assertTrue(revert_change(self.root, item))
        self.assertEqual(file.read_text(), 'old\n')

    def test_created_files_are_removed_and_missing_ones_count_as_done(self):
        file = self.root / 'n.txt'
        file.write_text('v1\n')
        item = {'path': 'n.txt', 'kind': 'created', 'before': '', 'after': 'v1\n'}
        self.assertTrue(revert_change(self.root, item))
        self.assertFalse(file.exists())
        self.assertTrue(revert_change(self.root, item))
        file.write_text('different\n')
        self.assertFalse(revert_change(self.root, item))
        self.assertTrue(file.exists())

    def test_paths_outside_the_folder_are_never_touched(self):
        outside = Path(tempfile.mkdtemp()) / 'x.txt'
        outside.write_text('keep\n')
        self.addCleanup(outside.unlink)
        item = {'path': str(outside), 'kind': 'created', 'before': '', 'after': 'keep\n'}
        self.assertFalse(revert_change(self.root, item))
        self.assertTrue(outside.exists())


class ExportTest(HomeCase):
    def test_markdown_has_messages_steps_diffs_and_footer(self):
        session = sessions.new_session('/work', 'make a file')
        session.events = [
            {'t': 'user', 'text': 'make a file', 'attached': ['a.py (2 lines)']},
            {'t': 'tool', 'name': 'write', 'detail': 'n.txt', 'status': 'finished'},
            {'t': 'tool', 'name': 'bash', 'detail': 'false', 'status': 'failed'},
            {'t': 'changes', 'items': [{'path': 'n.txt', 'kind': 'created', 'before': '', 'after': 'v1\n'}]},
            {'t': 'text', 'text': 'Done.'},
            {'t': 'footer', 'model': 'm', 'elapsed': 3.2, 'tokens': 1200},
            {'t': 'compact', 'summary': 'SUMMARY', 'before': 10, 'after': 1},
            {'t': 'error', 'text': 'boom'},
        ]
        text = to_markdown(session)
        for expected in ['# make a file', '## You', 'make a file', '_Attached: a.py (2 lines)_', '- `write` n.txt',
                         '- ✗ `bash` false', '**Created `n.txt`**', '+v1', '## Joy', 'Done.', '_m | 3s | 1200 tokens_',
                         'SUMMARY', '> boom']:
            self.assertIn(expected, text)
