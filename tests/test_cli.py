"""Exercise the real full-screen app without a physical terminal."""

import asyncio
import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from prompt_toolkit.formatted_text import to_plain_text

from harness import FOOTER, CliCase, wait_for
from joy.cli import format_date, main
from joy.sessions import list_sessions, session_name
from joy.transcript import Transcript


class CliTest(CliCase):
    def test_paste_ending_in_newline_stays_visible(self):
        inspected = []

        async def driver(app, pipe, transcript):
            pipe.send_text("\x1b[200~first line\r\nlast line\r\n\x1b[201~")
            await wait_for(lambda: app.current_buffer.text == "first line\nlast line\n")
            await asyncio.sleep(0.05)
            info = app.layout.current_window.render_info
            visible = "".join(
                to_plain_text(info.ui_content.get_line(index))
                for index in range(info.first_visible_line(), info.last_visible_line() + 1)
            )
            self.assertIn("first line", visible)
            self.assertIn("last line", visible)
            inspected.append(True)

        self.run_main(driver)
        self.assertTrue(inspected)

    def test_prompt_and_exit(self):
        requests = []
        live = []
        original_sleep = asyncio.sleep
        transcripts = []

        async def fake_reply(messages, model=None, connection=None, readonly=False, *args, **kwargs):
            requests.append(messages)
            await original_sleep(0.02)
            content = messages[-1]["content"]
            if content == "failed request":
                yield "Partial reply before failure."
                raise RuntimeError("OpenAI unavailable.")
            if content == "slow request":
                yield "Partial slow reply."
                await original_sleep(5)
            yield "An actual "
            await original_sleep(0.02)
            live.append(transcripts[0].plain())
            yield "assistant reply."

        async def driver(app, pipe, transcript):
            transcripts.append(transcript)

            async def finished(count):
                await wait_for(lambda: transcript.plain().count(FOOTER) >= count)

            pipe.send_text("hello\x1b\rworld\r")
            await finished(1)
            pipe.send_text("failed request\r")
            await wait_for(lambda: "OpenAI unavailable." in transcript.plain())
            pipe.send_text("[bold]literal[/bold]\r")
            await finished(2)
            pipe.send_text("slow request\r")
            await wait_for(lambda: "Partial slow reply." in transcript.plain())
            pipe.send_text("\x1b")
            await wait_for(lambda: "Response cancelled." in transcript.plain())
            pipe.send_text("draft for later")
            await wait_for(lambda: app.current_buffer.text == "draft for later")
            pipe.send_text("\x03")
            await wait_for(lambda: app.current_buffer.text == "")
            pipe.send_text("/pla\r")
            await wait_for(lambda: "Plan mode: Joy investigates" in transcript.plain())
            pipe.send_text("/nope\r")
            await wait_for(lambda: "Unknown command /nope" in transcript.plain())

        transcript = self.run_main(driver, fake_reply)
        text = transcript.plain()
        self.assertIn("Joy", text)
        self.assertRegex(text, r"› hello\s+world")
        self.assertIn("[bold]literal[/bold]", text)
        self.assertIn("OpenAI unavailable.", text)
        self.assertIn("Partial reply before failure.", text)
        self.assertIn("Response cancelled.", text)
        self.assertEqual(text.count("An actual assistant reply."), 2)
        self.assertTrue(any("An actual" in text for text in live))
        self.assertEqual([m["role"] for m in requests[2]], ["system", "user", "assistant", "user"])
        self.assertEqual(requests[2][1]["content"], "hello\nworld")
        self.assertEqual(requests[2][-1]["content"], "[bold]literal[/bold]")

    def test_transcript_scrolls_back_and_follows_new_output(self):
        transcript = Transcript()
        for number in range(30):
            transcript.add(f"line {number}")

        def visible(height):
            content = transcript.create_content(40, height)
            return [to_plain_text(content.get_line(index)) for index in range(content.line_count)]

        self.assertEqual(visible(10)[-1], "line 29")
        transcript.scroll(5)
        self.assertEqual(visible(10)[-1], "line 24")
        transcript.add("line 30")
        self.assertEqual(visible(10)[-1], "line 24")
        transcript.jump_to_end()
        self.assertEqual(visible(10)[-1], "line 30")
        transcript.scroll(1000)
        self.assertEqual(visible(10)[0], "line 0")

    def test_missing_key(self):
        output = StringIO()
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}), redirect_stdout(output):
            main([])
        self.assertIn("Set OPENAI_API_KEY", output.getvalue())

    def test_sessions_are_saved_continued_and_switched(self):
        requests = []

        async def fake_reply(messages, model=None, connection=None, readonly=False, *args, **kwargs):
            requests.append(messages)
            yield "Reply to " + messages[-1]["content"] + "."

        def ask(text):
            async def driver(app, pipe, transcript):
                pipe.send_text(text + "\r")
                await wait_for(lambda: FOOTER in transcript.plain())
            return driver

        folder = str(Path.cwd().resolve())
        self.run_main(ask("alpha topic"), fake_reply)
        self.run_main(ask("beta topic"), fake_reply)
        saved = list_sessions(folder)
        self.assertEqual([session.name for session in saved], ["beta topic", "alpha topic"])

        async def follow_up(app, pipe, transcript):
            await wait_for(lambda: "Reply to beta topic." in transcript.plain())
            pipe.send_text("more detail\r")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 2)

        self.run_main(follow_up, fake_reply, argv=["--continue"])
        self.assertEqual([m["role"] for m in requests[-1]], ["system", "user", "assistant", "user"])
        self.assertEqual(requests[-1][1]["content"], "beta topic")
        self.assertEqual(requests[-1][-1]["content"], "more detail")
        saved = list_sessions(folder)
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0].name, "beta topic")
        self.assertEqual(len(saved[0].messages), 4)

        async def switch(app, pipe, transcript):
            self.assertNotIn("alpha topic", transcript.plain())
            pipe.send_text("/session\r")
            await asyncio.sleep(0.1)
            pipe.send_text("alpha")
            await asyncio.sleep(0.1)
            pipe.send_text("\r")
            await wait_for(lambda: "Reply to alpha topic." in transcript.plain())
            self.assertNotIn("beta topic", transcript.plain())
            pipe.send_text("again\r")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 2)

        self.run_main(switch, fake_reply)
        self.assertEqual(requests[-1][1]["content"], "alpha topic")
        self.assertEqual(len(list_sessions(folder)), 2)

    def test_continue_without_a_session_starts_fresh(self):
        async def driver(app, pipe, transcript):
            await wait_for(lambda: "No earlier session" in transcript.plain())

        self.run_main(driver, argv=["-c"])

    def test_session_name_and_date(self):
        self.assertEqual(session_name("  fix   the\nbug  "), "fix the bug")
        self.assertEqual(len(session_name("x" * 200)), 80)
        self.assertRegex(format_date(1_700_000_000), r"^\w{3} \d{2}( \d{4}|, \d{2}:\d{2})$")
