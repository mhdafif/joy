import asyncio
import re
from pathlib import Path
from unittest.mock import patch

from prompt_toolkit.data_structures import Point
from prompt_toolkit.formatted_text import to_plain_text
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType

from harness import DOWN, ESCAPE, FOOTER, UP, CliCase, Replies, last_user_text, settle, wait_for
from joy.llm import Approval, Decision, ToolEvent
from joy.settings import load_settings
from joy.sessions import list_sessions, new_session, save_session
from joy.theme import active
from joy.tools import Change
from joy.transcript import Transcript
"""Feature behavior of the full-screen app: queue, modes, approvals, undo, compact, and more."""


async def say(pipe, text):
    pipe.send_text(text + "\r")
    await settle(0.05)


class QueueTest(CliCase):
    def blocked_first_reply(self):
        gates = []

        async def first(call):
            gates.append(asyncio.Event())
            await gates[0].wait()
            yield "first done"

        return Replies(first), gates

    def test_messages_sent_while_working_run_in_order_and_five_is_the_limit(self):
        replies, gates = self.blocked_first_reply()

        async def driver(app, pipe, transcript):
            await say(pipe, "one")
            await wait_for(lambda: len(replies.calls) == 1)
            for text in "abcde":
                await say(pipe, text)
            await say(pipe, "f")
            await wait_for(lambda: "The queue is full (5)" in transcript.plain())
            self.assertEqual(app.current_buffer.text, "f")
            gates[0].set()
            await wait_for(lambda: transcript.plain().count(FOOTER) == 6)

        self.run_main(driver, replies)
        self.assertEqual(replies.user_texts(), ["one", "a", "b", "c", "d", "e"])

    def test_up_pulls_the_newest_queued_message_back_into_the_input(self):
        replies, gates = self.blocked_first_reply()

        async def driver(app, pipe, transcript):
            await say(pipe, "one")
            await wait_for(lambda: len(replies.calls) == 1)
            await say(pipe, "a")
            await say(pipe, "b")
            pipe.send_text(UP)
            await wait_for(lambda: app.current_buffer.text == "b")
            gates[0].set()
            await wait_for(lambda: transcript.plain().count(FOOTER) == 2)

        self.run_main(driver, replies)
        self.assertEqual(replies.user_texts(), ["one", "a"])

    def test_commands_cannot_be_queued(self):
        replies, gates = self.blocked_first_reply()

        async def driver(app, pipe, transcript):
            await say(pipe, "one")
            await wait_for(lambda: len(replies.calls) == 1)
            await say(pipe, "/model")
            await wait_for(lambda: "Commands can run once the reply has finished." in transcript.plain())
            gates[0].set()
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            await settle(0.2)

        self.run_main(driver, replies)
        self.assertEqual(len(replies.calls), 1)

    def test_a_failed_reply_holds_the_queue_until_enter_is_pressed(self):
        gates = []

        async def failing(call):
            gates.append(asyncio.Event())
            await gates[0].wait()
            raise RuntimeError("boom")
            yield

        replies = Replies(failing)

        async def driver(app, pipe, transcript):
            await say(pipe, "one")
            await wait_for(lambda: len(replies.calls) == 1)
            await say(pipe, "a")
            gates[0].set()
            await wait_for(lambda: "queued message(s) are waiting" in transcript.plain())
            await settle(0.2)
            self.assertEqual(len(replies.calls), 1)
            await say(pipe, "")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)

        self.run_main(driver, replies)
        self.assertEqual(replies.user_texts(), ["one", "a"])

    def test_escape_stops_the_reply_and_the_next_queued_message_starts(self):
        async def forever(call):
            await asyncio.sleep(30)
            yield "never"

        replies = Replies(forever)

        async def driver(app, pipe, transcript):
            await say(pipe, "one")
            await wait_for(lambda: len(replies.calls) == 1)
            await say(pipe, "a")
            pipe.send_text(ESCAPE)
            await wait_for(lambda: "Response cancelled." in transcript.plain())
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)

        self.run_main(driver, replies)
        self.assertEqual(replies.user_texts(), ["one", "a"])


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

    def test_welcome_page_instructions_and_skill_commands(self):
        Path("AGENTS.md").write_text("Always answer in haiku.\n")
        skill = Path(".claude/skills/demo")
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: demo\ndescription: Demo skill that says hello\n---\nSay hello.\n")
        replies = Replies()

        async def driver(app, pipe, transcript):
            text = transcript.plain()
            for expected in ["Joy — a terminal coding agent", "Tab", "Instructions: AGENTS.md", "Skills: 1"]:
                self.assertIn(expected, text)
            await say(pipe, "@demo please")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            self.assertIn("› @demo please", transcript.plain())

        self.run_main(driver, replies)
        call = replies.calls[0]
        self.assertIn("Always answer in haiku.", call["messages"][0]["content"])
        self.assertIn("demo: Demo skill that says hello", call["messages"][0]["content"])
        self.assertIn('Use the "demo" skill', last_user_text(call["messages"]))
        self.assertIn("please", last_user_text(call["messages"]))
        self.assertEqual(list(call["skills"]), ["demo"])

    def test_the_skills_line_is_clickable_only_on_its_text_and_lists_every_skill(self):
        for name, description in [("alpha", "First helper"), ("beta", "Second helper")]:
            folder = Path(".claude/skills") / name
            folder.mkdir(parents=True)
            (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\nDo it.\n")

        def screen(app):
            parts = []
            for window in app.layout.find_all_windows():
                control = window.content
                if isinstance(control, FormattedTextControl) and callable(control.text):
                    parts.append(to_plain_text(control.text()))
            return "\n".join(parts)

        def mouse(kind, column, row):
            code = {"move": "35M", "click": "0m"}[kind]
            return f"\x1b[<{code[:-1]};{column};{row}{code[-1]}"

        async def driver(app, pipe, transcript):
            row = next(i for i, line in enumerate(transcript.plain(app.output.get_size().columns).splitlines()) if "Skills: 2" in line) + 1
            pipe.send_text(mouse("click", 60, row))
            await settle(0.2)
            self.assertNotIn("First helper", screen(app))
            pipe.send_text(mouse("click", 4, row + 1))
            await settle(0.2)
            self.assertNotIn("First helper", screen(app))
            pipe.send_text(mouse("move", 4, row))
            await settle(0.2)
            self.assertIn("Skills: 2 (click to view)", transcript.plain())
            pipe.send_text(mouse("move", 70, row))
            await settle(0.2)
            self.assertNotIn("click to view", transcript.plain())
            pipe.send_text(mouse("click", 4, row))
            await settle(0.2)
            listing = screen(app)
            for expected in ["Skills", "alpha", "First helper", "beta", "Second helper"]:
                self.assertIn(expected, listing)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: app.current_buffer.text == "@beta ")
            self.assertNotIn("Second helper", screen(app))

        self.run_main(driver, Replies())

    def test_skills_command_and_at_list_show_skills_but_slash_list_does_not(self):
        folder = Path(".claude/skills/alpha")
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("---\nname: alpha\ndescription: First helper\n---\nDo it.\n")
        Path("alpine.txt").write_text("x")

        def listing(app):
            for window in app.layout.find_all_windows():
                control = window.content
                if isinstance(control, FormattedTextControl) and callable(control.text):
                    rows = [line for line in to_plain_text(control.text()).splitlines() if line.strip()]
                    if rows and all(line.startswith((" /", " @", " No matching")) for line in rows):
                        return rows
            return []

        async def driver(app, pipe, transcript):
            pipe.send_text("/")
            await settle(0.2)
            self.assertNotIn("alpha", "".join(listing(app)))
            pipe.send_text("sk")
            await settle(0.2)
            self.assertEqual([row.split()[0] for row in listing(app)], ["/skills"])
            pipe.send_text("\x03")
            pipe.send_text("@al")
            await settle(0.2)
            rows = listing(app)
            self.assertEqual(rows[0].split()[0], "@alpha")
            self.assertIn("First helper", rows[0])
            self.assertEqual(rows[1].split()[0], "@alpine.txt")
            pipe.send_text("\t")
            await wait_for(lambda: app.current_buffer.text == "@alpha ")

        self.run_main(driver, Replies())

    def test_clicking_outside_any_modal_closes_it(self):
        def screen(app):
            parts = []
            for window in app.layout.find_all_windows():
                control = window.content
                if isinstance(control, FormattedTextControl) and callable(control.text):
                    parts.append(to_plain_text(control.text()))
            return "\n".join(parts)

        async def driver(app, pipe, transcript):
            await say(pipe, "/theme")
            await settle(0.25)
            self.assertIn("Cetak Biru", screen(app))
            pipe.send_text("\x1b[<0;1;1m")
            await settle(0.25)
            self.assertNotIn("Cetak Biru", screen(app))
            await say(pipe, "/connect")
            await settle(0.25)
            main_input = next(w for w in app.layout.find_all_windows() if isinstance(w.content, BufferControl) and w.content.buffer.multiline())
            self.assertIsNot(app.layout.current_window, main_input)
            pipe.send_text("\x1b[<0;1;1m")
            await settle(0.25)
            self.assertIs(app.layout.current_window, main_input)
            pipe.send_text("typed")
            await wait_for(lambda: app.current_buffer.text == "typed")

        self.run_main(driver, Replies())

    def test_tagged_files_are_attached_for_the_model_and_listed_for_you(self):
        Path("calc.py").write_text("def add(a, b):\n    return a + b\n")
        replies = Replies()

        async def driver(app, pipe, transcript):
            await say(pipe, "explain @calc.py ")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            self.assertIn("Attached calc.py (2 lines)", transcript.plain())

        self.run_main(driver, replies)
        sent = replies.user_texts()[0]
        self.assertIn("explain @calc.py", sent)
        self.assertIn('<file path="calc.py">\ndef add(a, b):', sent)

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

    def test_compact_replaces_the_history_with_a_summary(self):
        async def summarize(call):
            self.assertFalse(call["use_tools"])
            self.assertIn("Summarize our conversation", last_user_text(call["messages"]))
            yield "THE SUMMARY"

        replies = Replies(None, summarize)

        async def driver(app, pipe, transcript):
            await say(pipe, "first")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            await say(pipe, "/compact")
            await wait_for(lambda: "Conversation compacted" in transcript.plain())
            await say(pipe, "next")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 2)

        self.run_main(driver, replies)
        messages = replies.calls[2]["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user", "assistant", "user"])
        self.assertEqual(messages[1]["content"], "Summary of our earlier conversation:\n\nTHE SUMMARY")
        self.assertEqual(messages[3]["content"], "next")

    def test_compact_with_nothing_to_summarize_does_nothing(self):
        replies = Replies()

        async def driver(app, pipe, transcript):
            await say(pipe, "/compact")
            await wait_for(lambda: "nothing to compact" in transcript.plain())

        self.run_main(driver, replies)
        self.assertEqual(replies.calls, [])

    def test_opening_the_command_list_does_not_resize_the_conversation(self):
        replies = Replies()

        async def driver(app, pipe, transcript):
            window = next(w for w in app.layout.find_all_windows() if isinstance(w.content, Transcript))
            await settle(0.2)
            before = window.render_info.window_height
            pipe.send_text("/")
            await settle(0.2)
            self.assertEqual(window.render_info.window_height, before)

        self.run_main(driver, replies)

    def test_the_command_list_shows_five_rows_and_scrolls(self):
        seen = []

        def listing(app):
            for window in app.layout.find_all_windows():
                control = window.content
                if isinstance(control, FormattedTextControl) and callable(control.text):
                    text = to_plain_text(control.text())
                    rows = [line for line in text.splitlines() if line.strip()]
                    if rows and all(line.startswith(" /") for line in rows):
                        return rows
            return []

        async def driver(app, pipe, transcript):
            pipe.send_text("/")
            await settle(0.2)
            top = listing(app)
            self.assertEqual(len(top), 5)
            self.assertTrue(top[0].lstrip().startswith("/build"))
            self.assertIn("┃", "".join(top))
            for _ in range(7):
                pipe.send_text(DOWN)
            await settle(0.2)
            middle = listing(app)
            self.assertEqual(len(middle), 5)
            self.assertNotEqual(middle, top)
            pipe.send_text(UP)
            await settle(0.2)
            self.assertEqual(len(listing(app)), 5)
            for _ in range(20):
                pipe.send_text(DOWN)
            await settle(0.2)
            bottom = listing(app)
            self.assertEqual(len(bottom), 5)
            self.assertIn("/", bottom[-1])
            pipe.send_text("bu")
            await settle(0.2)
            narrowed = listing(app)
            self.assertEqual(len(narrowed), 1)
            self.assertNotIn("┃", "".join(narrowed))
            seen.append(top + middle + bottom)

        self.run_main(driver, Replies())
        self.assertTrue(seen)


class ApprovalTest(CliCase):
    def test_commands_ask_first_and_the_answers_are_remembered(self):
        outcomes = []

        def turn(command):
            async def behave(call):
                decision = Decision()
                yield Approval("bash", command, decision)
                while not decision.event.is_set():
                    await asyncio.sleep(0.01)
                outcomes.append((command, decision.allowed))
                yield "ok"
            return behave

        replies = Replies(*[turn(c) for c in ["touch a", "touch b", "touch b", "touch c", "touch d", "touch e"]])

        async def driver(app, pipe, transcript):
            async def ask(keys, number):
                await say(pipe, "go")
                await wait_for(lambda: len(replies.calls) == number)
                if keys is not None:
                    await settle(0.25)
                    pipe.send_text(keys)
                await wait_for(lambda: len(outcomes) == number)
                await wait_for(lambda: transcript.plain().count(FOOTER) == number)

            await ask("\r", 1)
            self.assertNotIn("allowed_commands", load_settings())
            await ask(DOWN + "\r", 2)
            self.assertEqual(load_settings()["allowed_commands"], ["touch b"])
            await ask(None, 3)
            await ask(ESCAPE, 4)
            await ask(DOWN + DOWN + "\r", 5)
            await ask(None, 6)

        self.run_main(driver, replies)
        self.assertEqual(outcomes, [
            ("touch a", True), ("touch b", True), ("touch b", True),
            ("touch c", False), ("touch d", True), ("touch e", True),
        ])

    def test_the_approval_prompt_floats_above_the_input_and_takes_keys_and_clicks(self):
        outcomes = []

        def turn(command):
            async def behave(call):
                decision = Decision()
                yield Approval("bash", command, decision)
                while not decision.event.is_set():
                    await asyncio.sleep(0.01)
                outcomes.append((command, decision.allowed))
                yield "ok"
            return behave

        replies = Replies(turn("rm -rf build"), turn("touch b"), turn("touch c"))

        def prompt(app):
            for window in app.layout.find_all_windows():
                control = window.content
                if isinstance(control, FormattedTextControl) and callable(control.text):
                    fragments = control.text()
                    if "Allow this command?" in to_plain_text(fragments):
                        return fragments
            return None

        async def driver(app, pipe, transcript):
            window = next(w for w in app.layout.find_all_windows() if isinstance(w.content, Transcript))
            await settle(0.2)
            before = window.render_info.window_height
            await say(pipe, "go")
            await wait_for(lambda: prompt(app) is not None)
            await settle(0.2)
            shown = to_plain_text(prompt(app))
            self.assertIn("rm -rf build", shown)
            for number, label in enumerate(["Allow once", "Always allow this exact command", "Allow all commands this session", "Deny"], 1):
                self.assertIn(f"{number}  {label}", shown)
            self.assertEqual(window.render_info.window_height, before)
            pipe.send_text("typed")
            await settle(0.1)
            self.assertEqual(app.current_buffer.text, "")
            pipe.send_text("4")
            await wait_for(lambda: len(outcomes) == 1 and prompt(app) is None)
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            await say(pipe, "go")
            await wait_for(lambda: prompt(app) is not None)
            handler = next(f[2] for f in prompt(app) if "Allow once" in f[1])
            handler(MouseEvent(Point(1, 0), MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
            await wait_for(lambda: len(outcomes) == 2 and prompt(app) is None)
            await wait_for(lambda: transcript.plain().count(FOOTER) == 2)
            await say(pipe, "go")
            await wait_for(lambda: prompt(app) is not None)
            pipe.send_text(ESCAPE)
            await wait_for(lambda: len(outcomes) == 3)

        self.run_main(driver, replies)
        self.assertEqual(outcomes, [("rm -rf build", False), ("touch b", True), ("touch c", False)])


class UndoTest(CliCase):
    def two_file_turns(self):
        async def write(call, content, kind, before):
            Path("n.txt").write_text(content)
            yield Change("n.txt", kind, before, content)
            yield "done"

        async def first(call):
            async for chunk in write(call, "v1\n", "created", ""):
                yield chunk

        async def second(call):
            async for chunk in write(call, "v2\n", "modified", "v1\n"):
                yield chunk

        return Replies(first, second)

    async def two_turns(self, pipe, transcript):
        await say(pipe, "make n")
        await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
        await say(pipe, "change n")
        await wait_for(lambda: transcript.plain().count(FOOTER) == 2)

    def test_the_task_window_can_copy_a_message(self):
        copied = []
        replies = self.two_file_turns()

        async def driver(app, pipe, transcript):
            await self.two_turns(pipe, transcript)
            await say(pipe, "/undo")
            await settle(0.25)
            pipe.send_text("\r")
            await wait_for(lambda: "Copied to the clipboard." in transcript.plain())

        with patch("joy.cli.copy_text", side_effect=lambda text: copied.append(text) or True):
            self.run_main(driver, replies)
        self.assertEqual(copied, ["change n"])

    def test_undo_restores_files_rewinds_the_chat_and_refills_the_input(self):
        replies = self.two_file_turns()

        async def driver(app, pipe, transcript):
            await self.two_turns(pipe, transcript)
            await say(pipe, "/undo")
            await settle(0.25)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: "Undid the task" in transcript.plain())
            self.assertEqual(Path("n.txt").read_text(), "v1\n")
            self.assertNotIn("› change n", transcript.plain())
            self.assertIn("› make n", transcript.plain())
            await wait_for(lambda: app.current_buffer.text == "change n")
            app.current_buffer.reset()
            await say(pipe, "retry")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 2)
            await say(pipe, "/undo")
            await settle(0.25)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: app.current_buffer.text == "retry")

        self.run_main(driver, replies)
        self.assertEqual([m["role"] for m in replies.calls[2]["messages"]], ["system", "user", "assistant", "user"])
        self.assertEqual(replies.calls[2]["messages"][-1]["content"], "retry")

    def test_undoing_the_first_task_removes_the_file_and_the_empty_session(self):
        replies = self.two_file_turns()

        async def driver(app, pipe, transcript):
            await self.two_turns(pipe, transcript)
            await say(pipe, "/undo")
            await settle(0.25)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: "Undid the task" in transcript.plain())
            await wait_for(lambda: app.current_buffer.text == "change n")
            app.current_buffer.reset()
            await say(pipe, "/undo")
            await settle(0.25)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: not Path("n.txt").exists())
            await wait_for(lambda: app.current_buffer.text == "make n")

        self.run_main(driver, replies)
        self.assertEqual(list_sessions(str(Path.cwd().resolve())), [])

    def test_files_you_changed_afterwards_are_left_alone(self):
        replies = self.two_file_turns()

        async def driver(app, pipe, transcript):
            await say(pipe, "make n")
            await wait_for(lambda: transcript.plain().count(FOOTER) == 1)
            Path("n.txt").write_text("my own edit\n")
            await say(pipe, "/undo")
            await settle(0.25)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: "Left alone because they changed afterwards: n.txt" in transcript.plain())
            self.assertEqual(Path("n.txt").read_text(), "my own edit\n")

        self.run_main(driver, replies)

    def test_messages_from_older_sessions_cannot_be_undone(self):
        session = new_session(str(Path.cwd().resolve()), "old task")
        session.events = [{"t": "user", "text": "old task"}, {"t": "text", "text": "old answer"}]
        session.messages = [{"role": "user", "content": "old task"}, {"role": "assistant", "content": "old answer"}]
        save_session(session)

        async def driver(app, pipe, transcript):
            await say(pipe, "/undo")
            await settle(0.25)
            pipe.send_text(DOWN + "\r")
            await wait_for(lambda: "cannot be undone" in transcript.plain())

        self.run_main(driver, Replies(), argv=["-c"])


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
