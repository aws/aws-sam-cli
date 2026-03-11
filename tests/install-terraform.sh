#!/bin/bash
# Install the latest Terraform for SAM CLI integration tests.
# Supports both Linux and Windows (Git Bash on GitHub Actions).
set -euo pipefail

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  echo "=== Installing Terraform on Windows via choco ==="
  choco install terraform -y
else
  echo "=== Installing Terraform on Linux ==="
  for i in {1..3}; do
    TER_VER=$(curl -s https://api.github.com/repos/hashicorp/terraform/releases/latest | grep tag_name | cut -d: -f2 | tr -d \"\,\v | awk '{$1=$1};1')
    if [ -n "$TER_VER" ]; then
      if wget -q "https://releases.hashicorp.com/terraform/${TER_VER}/terraform_${TER_VER}_linux_amd64.zip" -P /tmp; then
        sudo unzip -o -q /tmp/terraform_${TER_VER}_linux_amd64.zip -d /opt/terraform
        sudo mv /opt/terraform/terraform /usr/local/bin/
        break
      fi
    fi
    echo "Terraform installation attempt $i failed, retrying..."
    sleep 5
  done
fi

terraform -version
echo "=== Terraform installation complete ==="
