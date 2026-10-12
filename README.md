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
| `JOY_MODEL` | Model name sent in each request | `gpt-5.6-luna` |

To use OpenAI directly, set only `OPENAI_API_KEY` and leave the other two unset.
The endpoint must support the Responses API (`/v1/responses`); a 404 or 400 error
usually means it does not, or the model name is wrong.

Set these in your shell; `.env` files are not loaded automatically. Restarting with
`/restart` keeps them.

## Usage

- **Enter** — send a message once the current reply finishes.
- **Alt+Enter** (**Option+Enter** on Mac) or **Ctrl+J** — insert a newline. Option+Enter needs your terminal to send Option as Meta (VS Code: `terminal.integrated.macOptionIsMeta`); Ctrl+J works everywhere.
- **Ctrl+C** — cancel input or the pending reply.
- **Esc** — stop the running reply (shown as "esc to stop" while Joy works).
- **Ctrl+D** on empty input or **/exit** — exit.
- Type **/** to see command suggestions above the input; Up/Down move, Tab fills the highlighted command, Enter runs it.
- **/restart** — restart Joy to pick up code changes; conversation history is cleared.
- **/expand [n]** — show the full diff of a file change that was collapsed.

Every file change from `write` or `edit` is shown as a colored diff once the reply
finishes. Long diffs show the first 20 lines; `/expand` prints the most recent
collapsed one, or `/expand 3` a specific change by its number.

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
