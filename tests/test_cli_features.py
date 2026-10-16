from pathlib import Path
from harness import FOOTER, CliCase, Replies, settle, wait_for
from joy.settings import load_settings
from joy.sessions import list_sessions
from joy.theme import active
"""Feature behavior of the full-screen app: queue, modes, approvals, undo, compact, and more."""


async def say(pipe, text):
    pipe.send_text(text + "\r")
    await settle(0.05)


class ModesAndContextTest(CliCase):








    def test_new_and_clear_start_fresh_sessions(self):
        replies = Replies()

        async def driver(app, pipe, transcript):
            await say(pipe, "one")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            await say(pipe, "/new")
            await wait_for(lambda: "› one" not in transcript.plain())
            await say(pipe, "two")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            await say(pipe, "/clear")
            await wait_for(lambda: "› two" not in transcript.plain())

        self.run_main(driver, replies)
        self.assertEqual([m["role"] for m in replies.calls[1]["messages"]], ["system", "user"])
        self.assertEqual(sorted(s.name for s in list_sessions(str(Path.cwd().resolve()))), ["one", "two"])


class ConnectionsAndSettingsTest(CliCase):



    def test_theme_command_saves_the_choice_and_the_flag_only_tries_it(self):
        async def choose(app, pipe, transcript):
            await say(pipe, "/theme")
            await settle(0.25)
            pipe.send_text("\r")
            await wait_for(lambda: "Theme set to Ember." in transcript.plain())

        self.run_main(choose, Replies())
        self.assertEqual(load_settings()["theme"], "ember")
        self.assertEqual(active().key, "ember")

        async def look(app, pipe, transcript):
            await settle(0.1)

        self.run_main(look, Replies(), argv=["--theme", "moss"])
        self.assertEqual(active().key, "moss")
        self.assertEqual(load_settings()["theme"], "ember")
