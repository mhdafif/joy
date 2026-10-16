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

- **Enter** — send a message once the current reply finishes.
- **Page Up / Page Down** or the **mouse wheel** — scroll the conversation. New output keeps the view where it is while you read earlier messages; sending a message jumps back to the bottom.
- **Alt+Enter** (**Option+Enter** on Mac) or **Ctrl+J** — insert a newline. Option+Enter needs your terminal to send Option as Meta (VS Code: `terminal.integrated.macOptionIsMeta`); Ctrl+J works everywhere.
- **Ctrl+C** — cancel input or the pending reply.
- **Esc** — stop the running reply. While Joy works, a spinner line shows `Thinking…  esc to stop · 12s` with the elapsed time.
- **Ctrl+D** on empty input or **/exit** — exit.
- Type **/** to see command suggestions above the input, sorted alphabetically; Up/Down move, Tab fills the highlighted command, Enter runs it.
- **/session** — pick a saved session to continue. It opens in a window in the middle of the screen: sessions are listed newest first, named after your first message, with the date on the right; type to search, Up/Down to move, Enter to open, Esc to close.
- **/new** or **/clear** — start a new session without leaving Joy; the old one stays saved.
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

You can draft your next message while a reply streams. Conversation history lasts
until you exit. Cancelling stops further tool calls; completed file changes remain.
The API request may still finish in the background.

File tools operate inside the directory where you launch Joy. Bash runs with your
user permissions and a default 30-second timeout; it is not sandboxed.

Edit uses a unique text replacement with [Pi-style matching](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/src/core/tools/edit-diff.ts):
exact text first, then Unicode punctuation and trailing-whitespace normalization.
It preserves BOM/newline style, rejects ambiguous or unchanged replacements, and
returns a diff. Joy accepts one replacement per call; Pi also supports batches.

## Test

```sh
python -m unittest discover -s tests
```

Tests run without an API key or network access.
