"""Local tools and Pi-style matching, without network access."""

import json
import tempfile
import unittest
from pathlib import Path
from threading import Event
from joy.tools import _check_readonly, _replace, create_tools, is_readonly_command


class ToolsTest(unittest.TestCase):
    def test_pi_matching(self):
        cases = [
            ('a\r\nb\r\n', 'a\nb', 'c\nd', 'c\r\nd\r\n'),
            ('\ufeffa\r\n', 'a', 'b', '\ufeffb\r\n'),
            ('keep “this”  \nx = “old”  \nend  \n', 'x = "old"', 'x = "new"',
             'keep “this”  \nx = "new"\nend  \n'),
            ('a  \nb  \nc  \n', 'a\nb\n', 'z\n', 'z\nc  \n'),
            ('before\nﬁ = 1  ', 'fi = 1', 'fi = 2', 'before\nfi = 2'),
            ('x = “old”  \n', '“old”', '“new”', 'x = “new”  \n'),
        ]
        for original, old, new, expected in cases:
            with self.subTest(original=original, old=old):
                self.assertEqual(_replace(original, old, new), expected)
        for original, old, new in [('x x', 'x', 'y'), ('“x” "x"', '"x"', 'y'),
                                   ('a', 'missing', 'b'), ('a', '', 'b'),
                                   ('a', 'a', 'a'), ('a', ' ', 'b')]:
            with self.assertRaises(ValueError):
                _replace(original, old, new)

    def test_tools_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cancelled = Event()
            tools = create_tools(root, cancelled)

            def run(name, **arguments):
                return tools.execute({'function': {'name': name, 'arguments': json.dumps(arguments)}})[0]

            run('write', path='src/demo.py', content='print(“hello”)\n')
            self.assertIn('1: print', run('read', path='src/demo.py'))
            result = run('edit', path='src/demo.py', old_text='print("hello")', new_text='print("bye")')
            self.assertIn('+print("bye")', result)
            self.assertEqual((root / 'src/demo.py').read_text(), 'print("bye")\n')
            self.assertIn('bye', run('bash', command='python3 src/demo.py'))
            self.assertIn('exit code 7', run('bash', command='exit 7'))
            self.assertIn('Timed out', run('bash', command='sleep 5', timeout=1))
            for name, args in [('read', {'path': '../outside'}),
                               ('write', {'path': '../outside', 'content': 'no'}),
                               ('edit', {'path': 'src/demo.py', 'old_text': 'absent', 'new_text': 'no'})]:
                with self.assertRaises(ValueError):
                    run(name, **args)
            self.assertEqual((root / 'src/demo.py').read_text(), 'print("bye")\n')
            (root / 'escape').symlink_to(root.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                run('write', path='escape/outside', content='no')
            cancelled.set()
            with self.assertRaises(InterruptedError):
                run('write', path='cancelled', content='no')
            self.assertFalse((root / 'cancelled').exists())


class PlanModeTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        (self.root / 'a.txt').write_text('hello\n')

    def run_tool(self, tools, tool_name, **arguments):
        return tools.execute({'function': {'name': tool_name, 'arguments': json.dumps(arguments)}})[0]

    def test_read_only_commands_pass_and_everything_else_is_refused(self):
        for command in ['ls -la', 'cat a.txt', 'grep -rn hello . | head -5', 'git status',
                        'git log --oneline -5', "find . -name '*.py' | wc -l", 'rg foo src',
                        'grep -rn "/api/users" .']:
            with self.subTest(command=command):
                _check_readonly(self.root, command)
                self.assertTrue(is_readonly_command(self.root, command))
        for command in ['echo hi > x', 'rm a.txt', 'ls; rm a.txt', 'ls && ls', 'cat a.txt > b',
                        'sed -i s/a/b/ a.txt', 'find . -delete', 'git commit -m x', 'git checkout .',
                        'cat /etc/passwd', 'ls $(pwd)', 'ls `pwd`', 'python -c 1', 'FOO=1 ls',
                        'git diff --output=x', 'rg --pre sh foo', 'cat ~/.zshrc', 'ls\nrm a.txt',
                        'tee x', 'ls 2>&1', 'git branch newbranch', 'cat a.txt | sh', 'ls ..']:
            with self.subTest(command=command):
                with self.assertRaises(ValueError):
                    _check_readonly(self.root, command)
                self.assertFalse(is_readonly_command(self.root, command))

    def test_plan_mode_only_offers_read_and_a_guarded_bash(self):
        tools = create_tools(self.root, Event(), readonly=True)
        self.assertEqual([tool['function']['name'] for tool in tools.tools()], ['read', 'bash'])
        self.assertIn('hello', self.run_tool(tools, 'bash', command='cat a.txt'))
        with self.assertRaises(ValueError):
            self.run_tool(tools, 'bash', command='rm a.txt')
        self.assertTrue((self.root / 'a.txt').exists())

    def test_build_mode_offers_all_four_tools(self):
        tools = create_tools(self.root, Event())
        self.assertEqual([tool['function']['name'] for tool in tools.tools()], ['read', 'write', 'edit', 'bash'])


class ApprovalAndSkillTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def run_tool(self, tools, tool_name, **arguments):
        return tools.execute({'function': {'name': tool_name, 'arguments': json.dumps(arguments)}})[0]

    def test_bash_changes_are_reported(self):
        recorded = []
        tools = create_tools(self.root, Event(), recorded.append)
        (self.root / 'f.txt').write_text('one\ntwo\n')
        self.run_tool(tools, 'bash', command="sed -i.bak 's/two/TWO/' f.txt")
        self.run_tool(tools, 'bash', command='echo new > fresh.txt')
        self.assertEqual([(c.path, c.kind) for c in recorded if c.path in ('f.txt', 'fresh.txt')],
                         [('f.txt', 'modified'), ('fresh.txt', 'created')])
        changed = next(c for c in recorded if c.path == 'f.txt')
        self.assertEqual((changed.before, changed.after), ('one\ntwo\n', 'one\nTWO\n'))
