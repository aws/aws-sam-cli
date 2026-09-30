#!/bin/bash
# Install Python version(s) via uv and add them to GITHUB_PATH.
# Usage: bash tests/setup-python-uv.sh <version> [version...]
# Example:
#   bash tests/setup-python-uv.sh 3.10
#   bash tests/setup-python-uv.sh 3.9 3.10 3.11 3.12 3.13 3.14
set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 <python-version> [python-version...]"
  exit 1
fi

uv python install "$@"

# On Windows, uv installs Python executables to ~/.local/bin which may not be on PATH
if [[ "${RUNNER_OS:-}" == "Windows" && -d "$HOME/.local/bin" ]]; then
  echo "$HOME/.local/bin" >> "$GITHUB_PATH"
  export PATH="$HOME/.local/bin:$PATH"
fi

for ver in "$@"; do
  PYTHON_DIR=$(dirname "$(uv python find "$ver")")
  echo "$PYTHON_DIR" >> "$GITHUB_PATH"
  # On Windows, pip-installed scripts go into Scripts/ subdirectory
  if [ -d "$PYTHON_DIR/Scripts" ]; then
    echo "$PYTHON_DIR/Scripts" >> "$GITHUB_PATH"
  fi
done
