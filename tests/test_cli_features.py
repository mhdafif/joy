import re
from pathlib import Path
from unittest.mock import patch
from harness import DOWN, FOOTER, CliCase, Replies, settle, wait_for
from joy.llm import ToolEvent
from joy.settings import load_settings
from joy.sessions import list_sessions
from joy.theme import active
"""Feature behavior of the full-screen app: queue, modes, approvals, undo, compact, and more."""


async def say(pipe, text):
    pipe.send_text(text + "\r")
    await settle(0.05)


class ModesAndContextTest(CliCase):
    def test_tab_and_commands_switch_between_plan_and_build(self):
        replies = Replies()

        async def driver(app, pipe, transcript):
            pipe.send_text("\t")
            await wait_for(lambda: "Plan mode" in transcript.plain())
            await say(pipe, "investigate")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            await say(pipe, "/build")
            await wait_for(lambda: "Build mode" in transcript.plain())
            await say(pipe, "implement")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 2)
            await say(pipe, "/build")
            await wait_for(lambda: "Already in build mode" in transcript.plain())

        self.run_main(driver, replies)
        plan, build = replies.calls
        self.assertTrue(plan["readonly"])
        self.assertIn("plan mode", plan["messages"][0]["content"])
        self.assertFalse(build["readonly"])
        self.assertNotIn("plan mode", build["messages"][0]["content"])

    def test_plan_answers_that_looked_at_files_end_with_a_no_files_changed_note(self):
        async def reply(call):
            text = call["messages"][-1]["content"]
            if text != "chat":
                yield ToolEvent("read", "running", "calc.py")
                yield ToolEvent("read", "finished", "calc.py")
            yield {
                "plan": "1. Fix divide.",
                "chat": "Hi.",
                "refuse": "Plan mode is read-only, so I can't change files.",
                "says": "1. Fix it. No files were changed.",
                "build": "Done.",
            }[text]

        replies = Replies(reply, reply, reply, reply, reply)
        note = "Plan mode: no files changed."

        async def driver(app, pipe, transcript):
            await say(pipe, "/plan")
            for count, text in enumerate(["plan", "chat", "refuse", "says"], 1):
                await say(pipe, text)
                await wait_for(lambda: transcript.plain().count(FOOTER) == count)
            await say(pipe, "/build")
            await say(pipe, "build")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 5)
            plain = transcript.plain()
            self.assertEqual(plain.count(note), 1)
            self.assertRegex(plain, r"1\. Fix divide\.\s+Plan mode: no files changed\.\s+" + re.escape(FOOTER.split(" | ")[0]))
            self.assertRegex(plain, r"Hi\.\s+" + re.escape(FOOTER.split(" | ")[0]))

        self.run_main(driver, replies)
        system = replies.calls[0]["messages"][0]["content"]
        self.assertIn("read-only", system)
        self.assertIn("Press Tab to switch to Build", system)
        self.assertIn("never say that yourself", system)

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


    def test_connecting_then_choosing_a_model_sends_requests_to_that_connection(self):
        replies = Replies()

        async def driver(app, pipe, transcript):
            await say(pipe, "/connect")
            await settle(0.25)
            for value in ["r1", "http://127.0.0.1:9/v1/", "sk-test"]:
                await say(pipe, value)
                await settle(0.1)
            await wait_for(lambda: "Connected r1" in transcript.plain())
            await wait_for(lambda: "r1 offers 2 models" in transcript.plain())
            await say(pipe, "/model")
            await settle(0.4)
            pipe.send_text("m2")
            await settle(0.2)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: "Model set to m2 via r1." in transcript.plain())
            await say(pipe, "hi")
            await wait_for(lambda: transcript.plain().count(FOOTER.replace(FOOTER.split(" | ")[0], "m2")) == 1)

        with patch("joy.cli.list_models", side_effect=lambda connection=None: ["m1", "m2"]):
            self.run_main(driver, replies)
        call = replies.calls[0]
        self.assertEqual((call["model"], call["connection"].name, call["connection"].base_url),
                         ("m2", "r1", "http://127.0.0.1:9/v1"))
        self.assertEqual(load_settings()["selection"], {"connection": "r1", "model": "m2"})
        self.assertEqual(load_settings()["connections"][0]["api_key"], "sk-test")

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
