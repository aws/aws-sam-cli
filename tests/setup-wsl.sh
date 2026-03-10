#!/bin/bash
# Setup WSL 2 with Ubuntu 24.04 on a Windows GitHub Actions runner.
# This script runs from the Windows bash shell (Git Bash) and:
#   1. Installs WSL 2 with Ubuntu 24.04
#   2. Sets it as the default distribution
#   3. Configures wsl.conf for Docker volume mount compatibility
#   4. Updates packages and installs required dependencies
#
# This replaces the Vampire/setup-wsl@v6 GitHub Action with a self-contained script.
#
# Prerequisites:
#   - Windows runner with WSL feature available (GitHub Actions windows-latest)
#   - PowerShell available
set -e

DISTRO="Ubuntu-24.04"
WSL_INSTALL_PATH="D:\\wsl"

echo "=== Installing WSL 2 with ${DISTRO} ==="

# Install WSL and the Ubuntu distribution
# --web-download avoids Microsoft Store dependency
powershell.exe -Command "wsl --install ${DISTRO} --web-download --no-launch" || true

# Set WSL 2 as the default version
powershell.exe -Command "wsl --set-default-version 2"

# Set the installed distro as default
powershell.exe -Command "wsl --set-default ${DISTRO}"

echo "=== Configuring wsl.conf ==="

# Launch the distro to initialize it, then write wsl.conf
# The [automount] section ensures Windows drives mount at / instead of /mnt/
# which is required for Docker volume mount path compatibility
wsl -d "${DISTRO}" -- bash -c "
sudo tee /etc/wsl.conf > /dev/null << 'WSLCONF'
[automount]
root = /
options = \"metadata\"
WSLCONF
"

# Terminate and restart WSL so wsl.conf takes effect
powershell.exe -Command "wsl --terminate ${DISTRO}"
sleep 2

echo "=== Updating packages and installing dependencies ==="

wsl -d "${DISTRO}" -- bash -c "
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl net-tools
"

echo "=== WSL 2 setup complete ==="
wsl -d "${DISTRO}" -- bash -c "cat /etc/os-release | head -4"
