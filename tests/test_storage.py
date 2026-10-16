import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from joy import sessions
from joy.connections import (
    DEFAULT_NAME, Connection, load_connections, load_recent, load_selection, save_connection, save_selection,
)
from joy.settings import load_settings, save_settings
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
