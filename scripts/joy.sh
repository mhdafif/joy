#!/usr/bin/env bash

if ! (return 0 2>/dev/null); then
  echo "Source this script so the virtual environment stays active in your shell:" >&2
  echo "  source ${0}" >&2
  exit 1
fi

_joy_activate() {
  local source_path="$1" directory root env_file
  while [[ -L "$source_path" ]]; do
    directory="$(cd -P "$(dirname "$source_path")" && pwd)"
    source_path="$(readlink "$source_path")"
    [[ "$source_path" != /* ]] && source_path="$directory/$source_path"
  done
  root="$(cd -P "$(dirname "$source_path")/.." && pwd)"
  env_file="${JOY_ENV_FILE:-$root/.joy.env}"

  if [[ ! -f "$env_file" ]]; then
    cp "$root/scripts/joy.env.example" "$env_file"
    echo "Created $env_file" >&2
    echo "Edit it with your base URL, API key and model, then source this script again." >&2
    return 1
  fi

  if [[ ! -f "$root/.venv/bin/activate" ]]; then
    echo "No virtual environment at $root/.venv. See the Run section of the README." >&2
    return 1
  fi

  set -a
  source "$env_file"
  set +a

  if [[ -z "${OPENAI_BASE_URL:-}" ]]; then
    unset OPENAI_BASE_URL
  fi
  if [[ -z "${JOY_MODEL:-}" ]]; then
    unset JOY_MODEL
  fi

  if [[ -z "${OPENAI_API_KEY:-}" || "$OPENAI_API_KEY" == "your-api-key" ]]; then
    echo "Set OPENAI_API_KEY in $env_file" >&2
    return 1
  fi

  source "$root/.venv/bin/activate"
  echo "joy: ${OPENAI_BASE_URL:-https://api.openai.com/v1} · ${JOY_MODEL:-gpt-5.6-luna}" >&2
  echo "Virtual environment is active. Run joy to start." >&2
}

if [ -n "${ZSH_VERSION:-}" ]; then
  _joy_source="${(%):-%x}"
else
  _joy_source="${BASH_SOURCE[0]}"
fi
_joy_activate "$_joy_source" || {
  unset _joy_source
  unset -f _joy_activate
  return 1
}
unset _joy_source
unset -f _joy_activate
