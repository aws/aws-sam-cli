#!/bin/bash
# Setup Finch container runtime on Ubuntu
# This script stops Docker, installs Finch, and configures buildkit sockets.
set -e

echo "=== Stopping Docker ==="
sudo systemctl stop docker || true
sudo systemctl stop docker.socket || true
sudo systemctl disable docker || true
sudo systemctl disable docker.socket || true

echo "=== Installing Finch ==="
for i in {1..3}; do
    if curl -fsSL https://artifact.runfinch.com/deb/GPG_KEY.pub | sudo gpg --dearmor -o /usr/share/keyrings/runfinch-finch-archive-keyring.gpg; then
        break
    fi
    sleep 10
done

echo 'deb [signed-by=/usr/share/keyrings/runfinch-finch-archive-keyring.gpg arch=amd64] https://artifact.runfinch.com/deb noble main' | sudo tee /etc/apt/sources.list.d/runfinch-finch.list
sudo apt update
sudo apt install -y runfinch-finch

echo "=== Starting Finch services ==="
sudo systemctl enable --now finch
sudo systemctl enable --now finch-buildkit
sleep 3
sudo chmod 666 /var/run/finch.sock

echo "=== Waiting for Finch to be ready ==="
for i in {1..12}; do
    if sudo finch info >/dev/null 2>&1; then
        break
    fi
    sleep 5
done

echo "=== Configuring buildkit sockets ==="
sudo mkdir -p /run/buildkit-finch /run/buildkit-default /run/buildkit
sudo ln -sf /var/lib/finch/buildkit/buildkitd.sock /run/buildkit-finch/buildkitd.sock
sudo ln -sf /var/lib/finch/buildkit/buildkitd.sock /run/buildkit-default/buildkitd.sock
sudo ln -sf /var/lib/finch/buildkit/buildkitd.sock /run/buildkit/buildkitd.sock
sudo chmod 666 /var/lib/finch/buildkit/buildkitd.sock
sudo chmod 666 /run/buildkit-*/buildkitd.sock

echo "=== Installing QEMU for multi-arch support ==="
sudo finch run --privileged --rm tonistiigi/binfmt:master --install all

echo "=== Finch setup complete ==="
sudo finch info
sudo finch version
