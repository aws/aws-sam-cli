#!/bin/bash
# Install SAM CLI binary from a GitHub release, auto-detecting OS and architecture.
# Usage: ./test/install-sam-cli-binary.sh [<tag>]
#   If <tag> is provided (e.g. sam-cli-nightly), downloads from that release.
#   If omitted, downloads from the latest (non-pre-release) release.
set -euo pipefail

TAG="${1:-}"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

# Map to asset naming convention
case "$OS" in
  linux)
    case "$ARCH" in
      x86_64)  ASSET="aws-sam-cli-linux-x86_64.zip" ;;
      aarch64) ASSET="aws-sam-cli-linux-arm64.zip" ;;
      *)       echo "Unsupported Linux architecture: $ARCH"; exit 1 ;;
    esac
    ;;
  darwin)
    case "$ARCH" in
      x86_64) ASSET="aws-sam-cli-macos-x86_64.pkg" ;;
      arm64)  ASSET="aws-sam-cli-macos-arm64.pkg" ;;
      *)      echo "Unsupported macOS architecture: $ARCH"; exit 1 ;;
    esac
    ;;
  msys*|mingw*|cygwin*)
    ASSET="AWS_SAM_CLI_64_PY3.msi"
    ;;
  *)
    echo "Unsupported OS: $OS"; exit 1
    ;;
esac

echo "Detected OS=$OS ARCH=$ARCH -> downloading $ASSET"

# Download to a temp directory and clean up on exit
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

if [ -n "$TAG" ]; then
  gh release download "$TAG" --repo aws/aws-sam-cli --pattern "$ASSET" --clobber --dir "$TMPDIR"
else
  gh release download --repo aws/aws-sam-cli --pattern "$ASSET" --clobber --dir "$TMPDIR"
fi

# Install
case "$ASSET" in
  *.zip)
    unzip -o "$TMPDIR/$ASSET" -d "$TMPDIR/sam-installation"
    sudo "$TMPDIR/sam-installation/install" --update
    ;;
  *.pkg)
    sudo installer -pkg "$TMPDIR/$ASSET" -target /
    ;;
  *.msi)
    MSI_WIN="$(cygpath -w "$TMPDIR/$ASSET")"
    # Use PowerShell Start-Process for reliable non-interactive MSI install
    powershell.exe -Command "
      \$proc = Start-Process msiexec.exe -ArgumentList '/i', '$MSI_WIN', '/qn', '/norestart', '/l*v', 'D:\\msi-install.log' -Wait -PassThru
      if (\$proc.ExitCode -ne 0 -and \$proc.ExitCode -ne 3010) {
        Get-Content 'D:\\msi-install.log' -Tail 30 -ErrorAction SilentlyContinue
        exit \$proc.ExitCode
      }
    "
    # Nightly installs to AWSSAMCLI_NIGHTLY, release to AWSSAMCLI
    if [ -d "C:/Program Files/Amazon/AWSSAMCLI_NIGHTLY/bin" ]; then
      SAM_DIR="C:/Program Files/Amazon/AWSSAMCLI_NIGHTLY/bin"
    else
      SAM_DIR="C:/Program Files/Amazon/AWSSAMCLI/bin"
    fi
    if [ -n "${GITHUB_PATH:-}" ]; then
      echo "$SAM_DIR" >> "$GITHUB_PATH"
    fi
    export PATH="$SAM_DIR:$PATH"
    # Nightly binary is sam-nightly.cmd; create sam.cmd wrapper
    if [ -f "$SAM_DIR/sam-nightly.cmd" ]; then
      cp "$SAM_DIR/sam-nightly.cmd" "$SAM_DIR/sam.cmd"
    fi
    if [ -f "$SAM_DIR/sam-nightly.exe" ]; then
      cp "$SAM_DIR/sam-nightly.exe" "$SAM_DIR/sam.exe"
    fi
    ;;
esac

# Nightly installs as sam-nightly on Linux/macOS; rename to sam
if [ -f /usr/local/bin/sam-nightly ]; then
  sudo mv /usr/local/bin/sam-nightly /usr/local/bin/sam
fi

# On Windows, set SAM_WINDOWS_BINARY_PATH for tests
case "$OS" in
  msys*|mingw*|cygwin*)
    if [ -f "$SAM_DIR/sam-nightly.cmd" ]; then
      WIN_SAM_PATH="$(cygpath -w "$SAM_DIR/sam-nightly.cmd")"
    elif [ -f "$SAM_DIR/sam.cmd" ]; then
      WIN_SAM_PATH="$(cygpath -w "$SAM_DIR/sam.cmd")"
    fi
    if [ -n "${WIN_SAM_PATH:-}" ] && [ -n "${GITHUB_ENV:-}" ]; then
      echo "SAM_WINDOWS_BINARY_PATH=$WIN_SAM_PATH" >> "$GITHUB_ENV"
    fi
    "$SAM_DIR/sam.cmd" --version || "$SAM_DIR/sam-nightly.cmd" --version
    ;;
  *)
    sam --version
    ;;
esac
