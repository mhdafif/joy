# Joy

A terminal coding assistant built with Python, aisuite, prompt_toolkit, and Rich.
Chat with a model through any OpenAI-compatible endpoint, such as OpenAI directly or
a router like 9router, using streaming replies, Markdown, and conversation history.
Uses the Responses API with medium reasoning, preserving reasoning between tool calls.
The OpenAI SDK handles requests; aisuite defines and executes the four tools.

Includes four tools: **read** files, **write** files, **edit** text, and **bash**
to run commands and tests. Tool activity appears while replies stream.

## Run

Requires Python 3.10–3.13 and an API key for your endpoint.

```sh
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Then configure the endpoint in your shell and start Joy from the folder you want
to work in:

```sh
export OPENAI_BASE_URL="http://<your-9router-host>/v1"
export OPENAI_API_KEY="your-9router-key"
export JOY_MODEL="<model name as your router lists it>"
joy
```

| Variable | Purpose | Default |
| --- | --- | --- |
| `OPENAI_API_KEY` | API key for the endpoint (required) | none |
| `OPENAI_BASE_URL` | Endpoint, including the `/v1` suffix | OpenAI |
| `JOY_MODEL` | Model used on the Default connection until you pick one with `/model` | `gpt-5.6-luna` |
| `JOY_HOME` | Folder where Joy keeps its data (saved sessions and settings) | `~/.joy` |

To use OpenAI directly, set only `OPENAI_API_KEY` and leave the other two unset.
The endpoint must support the Responses API (`/v1/responses`); a 404 or 400 error
usually means it does not, or the model name is wrong.

### Launcher script

Instead of exporting by hand, keep the three values in one file and load them with
the script. It activates the virtual environment and sets the variables in your
current shell, but does not start Joy, so you run `joy` yourself (for example
`joy -c`). Source it from any folder, then change to the folder you want to work in:

```sh
source scripts/joy.sh
cd ~/my-project
joy
```

The first run creates `.joy.env` (git-ignored) from `scripts/joy.env.example`; edit
it, then source the script again. Empty `OPENAI_BASE_URL` or `JOY_MODEL` fall back to the defaults.
To switch setups, point at another file with `JOY_ENV_FILE=~/.joy-openai.env source scripts/joy.sh`,
or add an alias such as `alias joy-env="source $PWD/scripts/joy.sh"`. Running the script
without `source` only prints a reminder, because a script cannot activate an environment
in the shell that launched it.

Without the script, set these in your shell; `.env` files are not loaded automatically. Restarting with
`/restart` keeps them.

## Usage

Joy opens on its own full-screen page, like vim or OpenCode, and your terminal is restored when you exit. The conversation, diffs, and input all live on that page.

- **Enter** — send a message. While Joy is still working, Enter adds your message to a queue of up to 5, listed above the input, and each one is sent automatically when the previous reply finishes. Click a queued message to remove it, or press Up on an empty input to pull the newest one back into the input to edit. Stopping a reply with Esc moves on to the next queued message; if a reply fails, the queue waits and Enter on an empty input runs the next one. Commands (`/…`) cannot be queued.
- **Tab** — switch between **Build** and **Plan** mode (also `/build` and `/plan`); the current mode is shown on the input box. In **Plan** mode Joy only investigates: it can use `read` and a read-only `bash`, and answers with a plan instead of changing anything. If you ask it to actually change something ("create a file", "fix the bug"), it says in one short sentence that Plan mode is read-only and to press Tab for Build, instead of drafting a plan. When a Plan answer comes after Joy looked at your files or ran a command, it ends with an italic *Plan mode: no files changed.* line (unless the answer already says so); a plain chat answer such as "hi" does not. Switch back to Build and ask it to go ahead when you are happy with the plan; "apply the plan" applies the latest plan in the conversation.
- **Click a message you sent** — opens a small window with **Copy message** and **Undo**. The message lightens and shows `click for options` while the pointer is over it. Undo restores the files that task (and any later task) changed, rewinds the conversation to before that message, and puts the message back in the input so you can edit and resend it. A file you changed yourself afterwards is left alone and reported. Undo is not available for messages from sessions saved before this feature or from before a `/compact`.
- **Page Up / Page Down** or the **mouse wheel** — scroll the conversation. New output keeps the view where it is while you read earlier messages; sending a message jumps back to the bottom.
- **@file** — type `@` followed by part of a file or folder name to tag it: matching paths appear above the input (Up/Down to move, Tab or Enter to insert). When you send the message, the tagged files are attached for the model, so it does not have to search for them; a tagged folder attaches its file list. A line under your message shows what was attached. Binary or very large files are skipped, and an `@name` that is not a file is left as plain text. Files in `.gitignore` are not suggested.
- **Alt+Enter** (**Option+Enter** on Mac) or **Ctrl+J** — insert a newline. Option+Enter needs your terminal to send Option as Meta (VS Code: `terminal.integrated.macOptionIsMeta`); Ctrl+J works everywhere.
- **Ctrl+C** — cancel input or the pending reply.
- **Esc** — stop the running reply. While Joy works, a spinner line shows `Thinking…  esc to stop · 12s` with the elapsed time.
- **Ctrl+D** on empty input or **/exit** — exit.
- Type **/** to see command suggestions above the input, sorted alphabetically. The list shows at most five rows and scrolls (Up/Down or the mouse wheel) with a bar on the right when there are more; Tab fills the highlighted command, Enter runs it. The `@` file list behaves the same way.
- **/session** — pick a saved session to continue. It opens in a window in the middle of the screen: sessions are listed newest first, named after your first message, with the date on the right; type to search, Up/Down to move, Enter to open, Esc to close.
- **Click outside a window** — closes any centered window (the same as Esc).
- **/new** or **/clear** — start a new session without leaving Joy; the old one stays saved.
- **/undo** — open that same window for your latest message.
- **/compact** — ask the model to summarize the conversation so far and continue from the summary, which frees up context. The footer shows how much context is in use (`12.4k ctx`, with a `~` when it is an estimate).
- **/theme** — choose the color theme (Ember, the default, or Cetak Biru, Moss, Ocean, Orchid). Every color in Joy comes from the chosen palette, and the conversation is redrawn when you switch. The choice is saved in `~/.joy/settings.json`. To try one without saving it, start Joy with `joy --theme ember` (also `moss`, `ocean`, `orchid`, `cetak-biru`).
- **/model** — choose the model in a centered window (Ctrl+A inside it jumps to `/connect`). Models are grouped by connection, with the most recent picks in a **Recent** group at the top and `●` marking the one in use. Joy lists what each endpoint offers (`GET /v1/models`); type to search, Enter to select. If a list cannot be loaded, or the model is not listed, type its name and press Enter to use it with the current connection. The choice is saved and the current model (and connection, when you have more than one) is shown at the bottom right.
- **/connect** — add another endpoint. Joy asks for a group name, a base URL, and an API key (hidden while you type), checks that it can list models, and saves it. Using the same group name again updates that connection. The connection from `OPENAI_BASE_URL` / `OPENAI_API_KEY` always exists as **Default**.
- **Ctrl+O** — show or hide the details of every step. You can also click a step summary to open or close just that one.
- **/restart** — restart Joy to pick up code changes and start a fresh session; the old one stays saved.
- **/expand [n]** — show the full diff of a file change that was collapsed.

Joy captures the mouse for scrolling, so to select and copy text hold **Option** (Mac Terminal, iTerm2) or **Shift** (most other terminals) while dragging.

Every step Joy takes is printed in the conversation as it happens, for example `→ Read a.txt`, `← Edit a.txt`, `← Write b.txt`, and `$ npm test`; a failed step is marked with a red `✗` and the reason. Once the reply finishes, each run of steps folds into one readable line such as `▸ Read a.txt, edited a.txt and ran 1 command`; open it with Ctrl+O or a click to see every step. A run with a single step is shown as that one line instead of a folded group. When the answer is complete, a dim line under it shows the model, the time worked, and the tokens used, such as `gpt-5.6-luna | 12s | 4.9k tokens` (tokens are summed over every request the reply needed, and are left out if the endpoint does not report usage).

Every file change from `write` or `edit` is shown as a colored diff once the reply
finishes. Changes made through `bash` are shown too when the command names the file
(for example `sed -i … file`, `> file`, `tee file`); files a script changes without
being named in the command are not detected. Long diffs show the first 20 lines; `/expand` prints the most recent
collapsed one, or `/expand 3` a specific change by its number.

### Sessions

Connections and the selected model are stored in `~/.joy/settings.json`, including the API keys you enter with `/connect`, in plain text; the file is readable only by you, so treat it like a credentials file.

Every conversation is saved automatically to `~/.joy/sessions` (set `JOY_HOME` to change it) and belongs to the folder you launched Joy from. Start Joy with `joy --continue` (or `joy -c`) to pick up the last session in the current folder, including earlier messages, diffs, and what the model remembers. Use `/session` inside Joy to switch to an older one. Session files contain your conversation and file diffs, so treat them like your shell history.

Cancelling stops further tool calls; completed file changes remain.
The API request may still finish in the background.

### Approvals

In Build mode Joy asks before running a shell command that is not read-only. A panel appears just above the input (like the `/` list, so nothing moves) with the command and four choices: **Allow once**, **Always allow this exact command** (saved in `~/.joy/settings.json`), **Allow all commands this session**, or **Deny**. Pick with Up/Down and Enter, press 1-4, or click one; Esc denies, and the model is told the command was declined. The input is locked while the panel is open, so a stray Enter cannot approve a message you were typing. Read-only commands such as `ls`, `cat`, `grep`, and `git status` run without asking, and file edits are applied directly because they show as diffs and can be undone.

### Project instructions and skills

If the folder (or a parent up to the git root) has an `AGENTS.md` or `CLAUDE.md`, Joy adds it to its instructions; `~/.joy/AGENTS.md` applies everywhere. A **skill** is a folder with a `SKILL.md` (with `name` and `description` in its header) in `.joy/skills/` or `.claude/skills/` in the project, or in `~/.joy/skills/`. Joy lists the skills it finds, loads one on demand with a `skill` tool when a task matches, and you can call one yourself by tagging it with `@`, for example `@atomic-commit commit my changes`. Tagged skills and files are colored differently (skills in the theme's secondary color, files in its info color) in the suggestion list, in the input once they match a real skill or path, and in the message you sent. Typing `@` lists matching skills (with their descriptions) above the files, and `/skills` opens a window with all of them (Enter puts `@name` in the input). The welcome page shows how many were loaded; click the `Skills: n` text to open the same window.

While any window is open, the screen behind it is dimmed.

File tools operate inside the directory where you launch Joy. Bash runs with your
user permissions and a default 30-second timeout; it is not sandboxed. In Plan mode bash is limited to an allowlist of read-only commands (`ls`, `cat`, `grep`, `rg`, `find`, `tree`, `git status/log/diff/show`, and similar) that stay inside the workspace, with no redirects or command chaining; this is a safety net, not a sandbox.

Edit uses a unique text replacement with [Pi-style matching](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/tools/edit-diff.ts):
exact text first, then Unicode punctuation and trailing-whitespace normalization.
It preserves BOM/newline style, rejects ambiguous or unchanged replacements, and
returns a diff. Joy accepts one replacement per call; Pi also supports batches.

## Test

```sh
python -m unittest discover -s tests
```

Tests run without an API key or network access.
