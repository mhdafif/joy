from pathlib import Path
from harness import FOOTER, CliCase, Replies, settle, wait_for
from joy.sessions import list_sessions
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
