#!/bin/bash
# Install Rust toolchain and cargo-lambda for SAM CLI integration tests.
# Usage: ./tests/install-rust.sh [--uv] [CARGO_LAMBDA_VERSION]
#   --uv                Use uv-managed Python 3.11 (for setup-uv workflows)
#   CARGO_LAMBDA_VERSION defaults to env var or "v0.17.1"
set -euo pipefail

USE_UV=false
if [ "${1:-}" = "--uv" ]; then
  USE_UV=true
  shift
fi

CARGO_LAMBDA_VERSION="${1:-${CARGO_LAMBDA_VERSION:-v0.17.1}}"

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
else
  rustup target add x86_64-unknown-linux-gnu --toolchain stable
  rustup target add aarch64-unknown-linux-gnu --toolchain stable
fi

# Install cargo-lambda and ziglang
if [ "$USE_UV" = true ]; then
  PYTHON311="$(uv python find 3.11)"
  PYTHON311_BIN="$(dirname "$PYTHON311")"
  uv pip install --break-system-packages --python "$PYTHON311" "cargo-lambda==$CARGO_LAMBDA_VERSION" ziglang
  PYTHON_CMD="$PYTHON311"
  if [ -n "${GITHUB_PATH:-}" ]; then
    echo "$PYTHON311_BIN" >> "$GITHUB_PATH"
  fi
else
  python3.11 -m pip install "cargo-lambda==$CARGO_LAMBDA_VERSION" ziglang
  PYTHON_CMD="python3.11"
fi

# Create a zig wrapper so SAM CLI's cargo-lambda can find it
if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  # Place both zig (for bash/Git Bash) and zig.cmd (for cmd.exe) in C:\Windows
  printf '#!/bin/bash\nexec python3.11 -m ziglang "$@"\n' > /c/Windows/zig
  printf '@echo off\r\npython3.11 -m ziglang %%*\r\n' > /c/Windows/zig.cmd
else
  printf '#!/bin/bash\nexec %s -m ziglang "$@"\n' "$PYTHON_CMD" | sudo tee /usr/local/bin/zig > /dev/null
  sudo chmod +x /usr/local/bin/zig
fi

rustc -V
cargo -V
zig version
