#!/bin/bash
# Full WSL2 + Docker setup for Windows GitHub Actions runners.
# This script runs from the Windows bash shell (Git Bash) and:
#   1. Fixes CRLF line endings in test data scripts
#   2. Stops the Windows Docker Engine
#   3. Installs WSL 2 with Ubuntu 24.04
#   4. Configures wsl.conf for Docker volume mount compatibility
#   5. Installs Docker inside WSL2 (delegates to setup_wsl2_docker.sh)
#   6. Exports DOCKER_HOST and TEMP to GITHUB_ENV
#
# Prerequisites:
#   - Windows runner with WSL feature available (GitHub Actions windows-latest)
#   - PowerShell available
#   - tests/setup_wsl2_docker.sh present in the repo
set -e

DISTRO="Ubuntu-24.04"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Step 1: Fix CRLF in test data ──
# Windows git checkout may add \r to shell/python scripts, breaking execution inside Linux containers
echo "=== Fixing CRLF line endings in test data ==="
find tests/integration/testdata -name "*.sh" -exec sed -i 's/\r$//' {} +
find tests/integration/testdata -name "*.py" -exec sed -i 's/\r$//' {} +

# ── Step 2: Stop Windows Docker Engine ──
echo "=== Stopping Windows Docker Engine ==="
powershell.exe -Command "
  Start-Job {
    Stop-Service docker -Force -ErrorAction SilentlyContinue
    Get-Process 'Docker Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process 'com.docker.backend' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process 'com.docker.service' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
  } | Out-Null
"

# ── Step 3: Install and configure WSL 2 ──
echo "=== Installing WSL 2 with ${DISTRO} ==="

# Install WSL and the Ubuntu distribution
# --web-download avoids Microsoft Store dependency
powershell.exe -Command "wsl --install ${DISTRO} --web-download --no-launch" || true

# Set WSL 2 as the default version
powershell.exe -Command "wsl --set-default-version 2"

# Set the installed distro as default
powershell.exe -Command "wsl --set-default ${DISTRO}"

echo "=== Configuring wsl.conf ==="

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

# ── Step 4: Install Docker inside WSL2 ──
echo "=== Installing Docker inside WSL2 ==="
# Fix CRLF in the docker setup script, then run it inside WSL
wsl -d "${DISTRO}" -- bash -c "
  sed -i 's/\r$//' tests/setup_wsl2_docker.sh
  bash tests/setup_wsl2_docker.sh
"

# ── Step 5: Export DOCKER_HOST and TEMP for subsequent workflow steps ──
echo "=== Configuring DOCKER_HOST and TEMP ==="
WSL_IP=$(powershell.exe -Command "(wsl hostname -I).Trim().Split(' ')[0]" | tr -d '\r')
echo "WSL2 IP: ${WSL_IP}"
echo "DOCKER_HOST=tcp://${WSL_IP}:2375" >> "$GITHUB_ENV"

powershell.exe -Command "New-Item -ItemType Directory -Force -Path 'D:\Temp' | Out-Null"
echo "TEMP=D:\Temp" >> "$GITHUB_ENV"

echo "=== WSL2 + Docker setup complete ==="
