#!/bin/bash
# Install Rust toolchain and cargo-lambda for SAM CLI integration tests.
# Usage: ./tests/install-rust.sh [--uv]
#   --uv                Use uv-managed Python 3.11 (for setup-uv workflows)
# cargo-lambda and zig versions come from the rust-tests extra in pyproject.toml.
set -euo pipefail

USE_UV=false
if [ "${1:-}" = "--uv" ]; then
  USE_UV=true
  shift
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Install rustup if not present
if ! command -v rustup &> /dev/null; then
  curl --proto '=https' --tlsv1.2 --retry 10 --retry-connrefused -fsSL https://sh.rustup.rs | sh -s -- --default-toolchain none -y
  # source cargo env (file doesn't exist on Windows where Rust is pre-installed)
  if [ -f "$HOME/.cargo/env" ]; then
    source "$HOME/.cargo/env"
  fi
  if [ -n "${GITHUB_PATH:-}" ]; then
    echo "${CARGO_HOME:-$HOME/.cargo}/bin" >> "$GITHUB_PATH"
  fi
fi

rustup toolchain install stable --profile minimal --no-self-update
rustup default stable

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  # On Windows, add Windows-native targets
  rustup target add x86_64-pc-windows-msvc --toolchain stable || true
  # Also pre-install the Linux cross-compile targets used by cargo-lambda.
  # If cargo-lambda has to install these on demand during parallel test runs
  # (pytest -n 2), concurrent rustup invocations can produce a partial/corrupt
  # target install (e.g., "can't find crate for `adler2`"). Pre-installing here
  # avoids that race.
  rustup target add x86_64-unknown-linux-gnu --toolchain stable
  rustup target add aarch64-unknown-linux-gnu --toolchain stable
else
  rustup target add x86_64-unknown-linux-gnu --toolchain stable
  rustup target add aarch64-unknown-linux-gnu --toolchain stable
fi

# Install cargo-lambda and ziglang at the versions pinned in pyproject.toml's rust-tests extra
read_rust_tools() {
  "$1" -c 'import sys,tomllib;print(" ".join(tomllib.load(open(sys.argv[1],"rb"))["project"]["optional-dependencies"]["rust-tests"]))' "$REPO_ROOT/pyproject.toml"
}

if [ "$USE_UV" = true ]; then
  PYTHON311="$(uv python find 3.11)"
  PYTHON311_BIN="$(dirname "$PYTHON311")"
  # shellcheck disable=SC2046  # deliberate word splitting: one pip arg per pinned package
  uv pip install --break-system-packages --python "$PYTHON311" $(read_rust_tools "$PYTHON311")
  PYTHON_CMD="$PYTHON311"
  if [ -n "${GITHUB_PATH:-}" ]; then
    echo "$PYTHON311_BIN" >> "$GITHUB_PATH"
  fi
else
  # shellcheck disable=SC2046
  python3.11 -m pip install $(read_rust_tools python3.11)
  PYTHON_CMD="python3.11"
fi

# Create a zig wrapper so SAM CLI's cargo-lambda can find it
if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  # Pinned so choco's zig cannot float; the check below is on version, not mere presence, so
  # a zig already on PATH cannot win over the pin.
  ZIG_VERSION="$(read_rust_tools "$PYTHON_CMD" | tr ' ' '\n' | sed -n 's/^ziglang==//p')"
  choco install zig --version="$ZIG_VERSION" --no-progress -y 2>/dev/null || true
  # Fallback: create wrappers using the Python that has ziglang installed
  if ! zig version 2>/dev/null | grep -qx "$ZIG_VERSION"; then
    ZIG_PYTHON="$PYTHON_CMD"
    printf '#!/bin/bash\nexec "%s" -m ziglang "$@"\n' "$ZIG_PYTHON" > /c/Windows/zig
    printf '@echo off\r\n"%s" -m ziglang %%*\r\n' "$ZIG_PYTHON" > /c/Windows/zig.cmd
  fi
else
  printf '#!/bin/bash\nexec %s -m ziglang "$@"\n' "$PYTHON_CMD" | sudo tee /usr/local/bin/zig > /dev/null
  sudo chmod +x /usr/local/bin/zig
fi

rustc -V
cargo -V
zig version
