#!/bin/bash
# Free up disk space on CI runners if root partition has less than 50GB free.
# Removes common unused resources that ship with GitHub Actions runners.
set -e

echo "=== Disk usage before cleanup ==="
df -h

ROOT_FREE_GB=$(df -BG / | awk 'NR==2 {gsub("G",""); print $4}')
echo "Free disk space on root: ${ROOT_FREE_GB}GB"

if [ "$ROOT_FREE_GB" -ge 50 ]; then
    echo "Sufficient disk space available, skipping cleanup."
    exit 0
fi

# If /mnt is mounted and has > 50GB free, redirect temp dirs there
if mountpoint -q /mnt 2>/dev/null; then
    MNT_FREE_GB=$(df -BG /mnt | awk 'NR==2 {gsub("G",""); print $4}')
    if [ "$MNT_FREE_GB" -gt 50 ]; then
        echo "Root has ${ROOT_FREE_GB}GB free, /mnt has ${MNT_FREE_GB}GB free. Redirecting temp dirs to /mnt."
        sudo mkdir -p /mnt/tmp
        sudo chmod 1777 /mnt/tmp
        echo "TMPDIR=/mnt/tmp" >> "$GITHUB_ENV"
        echo "TEMP=/mnt/tmp" >> "$GITHUB_ENV"
        echo "TMP=/mnt/tmp" >> "$GITHUB_ENV"
        echo "RUNNER_TEMP=/mnt/tmp" >> "$GITHUB_ENV"

        # # Move Docker data-root to /mnt to free root partition
        # echo "Relocating Docker storage to /mnt/docker..."
        # sudo systemctl stop docker || true
        # sudo mkdir -p /mnt/docker
        # sudo mkdir -p /etc/docker
        # echo '{"data-root": "/mnt/docker"}' | sudo tee /etc/docker/daemon.json > /dev/null
        # if [ -d /var/lib/docker ]; then
        #     sudo rsync -a /var/lib/docker/ /mnt/docker/ 2>/dev/null || true
        #     sudo rm -rf /var/lib/docker
        # fi
        # sudo systemctl start docker || true
    fi
fi

echo "Free space below 50GB, cleaning up..."

# Reduce swap to 1GB (only use /mnt if it exists)
sudo swapoff -a || true
if mountpoint -q /mnt 2>/dev/null; then
    sudo fallocate -l 1G /mnt/swapfile || true
    sudo chmod 600 /mnt/swapfile || true
    sudo mkswap /mnt/swapfile || true
    sudo swapon /mnt/swapfile || true
fi

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
