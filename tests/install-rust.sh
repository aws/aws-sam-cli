#!/bin/bash
# Install Rust toolchain and cargo-lambda for SAM CLI integration tests.
# Usage: ./tests/install-rust.sh [CARGO_LAMBDA_VERSION]
#   CARGO_LAMBDA_VERSION defaults to env var or "v0.17.1"
set -euo pipefail

CARGO_LAMBDA_VERSION="${1:-${CARGO_LAMBDA_VERSION:-v0.17.1}}"

# Install rustup if not present
if ! command -v rustup &> /dev/null; then
  curl --proto '=https' --tlsv1.2 --retry 10 --retry-connrefused -fsSL https://sh.rustup.rs | sh -s -- --default-toolchain none -y
  source "$HOME/.cargo/env"
  if [ -n "${GITHUB_PATH:-}" ]; then
    echo "${CARGO_HOME:-$HOME/.cargo}/bin" >> "$GITHUB_PATH"
  fi
fi

rustup toolchain install stable --profile minimal --no-self-update
rustup default stable
rustup target add x86_64-unknown-linux-gnu --toolchain stable
rustup target add aarch64-unknown-linux-gnu --toolchain stable

# Install cargo-lambda and ziglang
python3.11 -m pip install "cargo-lambda==$CARGO_LAMBDA_VERSION"

# Create a zig wrapper so SAM CLI's cargo-lambda can find it
printf '#!/bin/bash\nexec python3.11 -m ziglang "$@"\n' | sudo tee /usr/local/bin/zig > /dev/null
sudo chmod +x /usr/local/bin/zig

rustc -V
cargo -V
zig version
