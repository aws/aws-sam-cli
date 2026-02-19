#!/bin/bash
# Free up disk space on CI runners if root partition has less than 25GB free.
# Removes common unused resources that ship with GitHub Actions runners.
set -e

echo "=== Disk usage before cleanup ==="
df -h /

FREE_GB=$(df -BG / | awk 'NR==2 {gsub("G",""); print $4}')
echo "Free disk space: ${FREE_GB}GB"

if [ "$FREE_GB" -ge 25 ]; then
    echo "Sufficient disk space available, skipping cleanup."
    exit 0
fi

echo "Free space below 25GB, cleaning up..."

# Reduce swap to 1GB
sudo swapoff -a || true
sudo fallocate -l 1G /mnt/swapfile || true
sudo chmod 600 /mnt/swapfile || true
sudo mkswap /mnt/swapfile || true
sudo swapon /mnt/swapfile || true

# Reduce system reserved space to 512MB
sudo tune2fs -m 0.5 $(df / | awk 'NR==2 {print $1}') 2>/dev/null || true

# Remove large unused packages (run in background with nohup)
nohup sudo rm -rf /usr/local/lib/android > /dev/null 2>&1 &
nohup sudo rm -rf /opt/ghc > /dev/null 2>&1 &
nohup sudo rm -rf /opt/hostedtoolcache/CodeQL > /dev/null 2>&1 &
nohup sudo rm -rf /usr/local/share/powershell > /dev/null 2>&1 &

# Clean apt cache
nohup sudo apt-get clean > /dev/null 2>&1 &

# Remove existing Docker images to free space
nohup docker system prune -af --volumes > /dev/null 2>&1 &

echo "Cleanup jobs started in background."
