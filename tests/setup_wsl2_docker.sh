#!/bin/bash
# Setup Docker Engine inside WSL2 on a Windows GitHub Actions runner.
# This script runs INSIDE WSL2 (via wsl-bash shell) and:
#   1. Installs Docker Engine from the official Docker repository
#   2. Restarts Docker to listen on TCP port 2375 so Windows can connect
#
# After running this script, the caller must set DOCKER_HOST on the Windows side
# to point to the WSL2 IP address (tcp://<wsl2-ip>:2375).
#
# Prerequisites:
#   - WSL2 with Ubuntu installed
#   - wsl.conf configured with [automount] root = / (for Docker volume mount path compatibility)
set -e

echo "=== Installing Docker Engine in WSL2 ==="

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the Docker repository to Apt sources
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker packages
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Ensure /etc/resolv.conf exists as a real file (not a broken symlink).
# WSL2 may create it as a symlink to a non-existent Windows-managed file,
# which causes Docker's containerd to fail when mounting it into containers.
sudo rm -f /etc/resolv.conf 2>/dev/null || true
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null

echo "=== Configuring Docker daemon to listen on TCP port 2375 ==="

# Stop Docker service and socket completely
sudo systemctl stop docker.service || sudo service docker stop || true
sudo systemctl stop docker.socket || true
sleep 2

# Kill any remaining dockerd processes
sudo pkill -9 dockerd || true
sleep 1

# Remove stale socket file if it exists
sudo rm -f /var/run/docker.sock

# Start dockerd with both unix socket and TCP listeners
# --tls=false suppresses the deprecation delay for non-TLS TCP binding
sudo dockerd --tls=false --host unix:///var/run/docker.sock --host tcp://0.0.0.0:2375 &

# Wait for Docker to be ready (poll up to 30 seconds)
echo "Waiting for Docker daemon to be ready..."
for i in $(seq 1 30); do
  if sudo docker info > /dev/null 2>&1; then
    echo "Docker daemon is ready after ${i}s"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "ERROR: Docker daemon failed to start within 30 seconds"
    exit 1
  fi
  sleep 1
done

# Register QEMU binfmt handlers for ARM64 emulation
# This must run inside WSL2 (not from Windows) because --privileged containers
# have issues with devpts/resolv.conf when run via TCP from Windows.
echo "=== Setting up QEMU for ARM64 emulation ==="
sudo docker run --rm --privileged multiarch/qemu-user-static --reset -p yes || \
  echo "WARNING: QEMU setup failed, ARM64 builds may not work"

echo "=== Docker Engine installed and listening on TCP port 2375 ==="
sudo docker info
