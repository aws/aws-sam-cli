#!/bin/bash
# Set up a pytest venv with test dependencies (cross-platform).
# Also exports SCRIPT_PY to GITHUB_ENV and adds Scripts dir to GITHUB_PATH on Windows.
set -eo pipefail

echo "=== UV_PYTHON resolved to: $(uv python find ${UV_PYTHON:-3.11}) ==="

if [ "${RUNNER_OS:-}" == "Windows" ] || [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == MSYS* ]]; then
  python3.11 -m venv "$HOME/pytest"
  VENV_PY="$HOME/pytest/Scripts/python.exe"
  SAM_CLI_DEV=1 uv pip install --python "$VENV_PY" -e '.[dev]'
  "$HOME/pytest/Scripts/pytest" --version
  if [ -n "${GITHUB_ENV:-}" ]; then
    echo "SCRIPT_PY=$VENV_PY" >> "$GITHUB_ENV"
    echo "$HOME/pytest/Scripts" >> "$GITHUB_PATH"
  fi
else
  python3.11 -m venv "$HOME/pytest"
  VENV_PY="$HOME/pytest/bin/python3"
  SAM_CLI_DEV=1 uv pip install --python "$VENV_PY" -e '.[dev]'
  sudo ln -sf "$HOME/pytest/bin/pytest" /usr/local/bin/pytest 2>/dev/null || true
  "$HOME/pytest/bin/pytest" --version
  if [ -n "${GITHUB_ENV:-}" ]; then
    echo "SCRIPT_PY=$VENV_PY" >> "$GITHUB_ENV"
  fi
fi
