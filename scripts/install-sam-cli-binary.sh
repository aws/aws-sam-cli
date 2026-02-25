#!/bin/bash
# Install SAM CLI binary from a GitHub release, auto-detecting OS and architecture.
# Usage: ./scripts/install-sam-cli-binary.sh [<tag>]
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
    # Nightly installs as sam-nightly; rename to sam
    if [ -f /usr/local/bin/sam-nightly ]; then
      sudo mv /usr/local/bin/sam-nightly /usr/local/bin/sam
    fi
    ;;
  *.pkg)
    sudo installer -pkg "$TMPDIR/$ASSET" -target /
    # Nightly installs as sam-nightly; rename to sam
    if [ -f /usr/local/bin/sam-nightly ]; then
      sudo mv /usr/local/bin/sam-nightly /usr/local/bin/sam
    fi
    ;;
esac

sam --version
