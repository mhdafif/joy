import asyncio
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from joy.cli import main
from joy.llm import MODEL
from joy.transcript import Transcript
"""Shared helpers for driving the full-screen app without a terminal."""




FOOTER = MODEL.split(":", 1)[1] + " | "
UP, DOWN, ESCAPE, ENTER = "\x1b[A", "\x1b[B", "\x1b", "\r"


async def wait_for(predicate, timeout=3.0):
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("Timed out waiting for the interface.")
        await asyncio.sleep(0.01)


async def settle(delay=0.15):
    await asyncio.sleep(delay)


def last_user_text(messages):
    return next(message["content"] for message in reversed(messages) if message["role"] == "user")


class Replies:
    def __init__(self, *behaviors):
        self.calls = []
        self.behaviors = list(behaviors)

    def __call__(self, messages, model=None, connection=None, readonly=False, skills=None,
                 ask_approval=False, use_tools=True):
        call = {"messages": messages, "model": model, "connection": connection, "readonly": readonly,
                "skills": skills, "use_tools": use_tools}
        self.calls.append(call)
        index = len(self.calls) - 1
        behavior = self.behaviors[index] if index < len(self.behaviors) and self.behaviors[index] else self.echo
        return behavior(call)

    @staticmethod
    async def echo(call):
        yield "Reply to " + last_user_text(call["messages"]) + "."

    def user_texts(self):
        return [last_user_text(call["messages"]) for call in self.calls]


class CliCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        self.addCleanup(self.workspace.cleanup)
        environment = patch.dict(os.environ, {"JOY_HOME": self.home.name})
        environment.start()
        self.addCleanup(environment.stop)
        previous = os.getcwd()
        os.chdir(self.workspace.name)
        self.addCleanup(os.chdir, previous)

    def run_main(self, driver, reply=None, argv=(), patches=()):
        transcripts = []

        def make_transcript():
            transcripts.append(Transcript())
            return transcripts[0]

        failures = []
        with create_pipe_input() as pipe:
            class DrivenApplication(Application):
                def run(self, *args, **kwargs):
                    async def drive():
                        try:
                            await driver(self, pipe, transcripts[0])
                        except BaseException as error:
                            failures.append(error)
                        finally:
                            if not self.is_done:
                                self.exit()

                    kwargs["pre_run"] = lambda: self.create_background_task(drive())
                    return super().run(*args, **kwargs)

            active = [
                patch("joy.cli.Application", DrivenApplication),
                patch("joy.cli.Transcript", side_effect=make_transcript),
                patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}),
                *patches,
            ]
            if reply is not None:
                active.append(patch("joy.cli.stream_reply", side_effect=reply))
            with create_app_session(input=pipe, output=DummyOutput()), redirect_stdout(StringIO()):
                for item in active:
                    item.start()
                try:
                    main(list(argv))
                finally:
                    for item in reversed(active):
                        item.stop()
        if failures:
            raise failures[0]
        return transcripts[0]
