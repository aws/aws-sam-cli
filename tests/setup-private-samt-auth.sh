#!/bin/bash
# Configure read-only access to the private SAM Transform repository.
#
# pyproject.toml carries a direct reference to aws-sam-translator on a branch of
# aws/PRIVATE-aws-sam-development, because the released version has no knowledge of
# AcceleratorConfig. GITHUB_TOKEN is scoped to this repository only and cannot clone
# that one, so dependency installation needs the deploy key held in the
# SAM_TRANSFORM_SSH_PRIVATE_KEY secret.
#
# Rewriting only that one repository's URL keeps every other github.com fetch on HTTPS,
# so the checkout credential this workflow already has is left untouched.
#
# Usage (the secret must be exported by the caller):
#   env SAM_TRANSFORM_SSH_PRIVATE_KEY="${{ secrets.SAM_TRANSFORM_SSH_PRIVATE_KEY }}" \
#       bash tests/setup-private-samt-auth.sh

set -euo pipefail

PRIVATE_REPO_PATH="aws/PRIVATE-aws-sam-development"
KEY_NAME="sam_transform_deploy_key"
KEY_PATH="$HOME/.ssh/$KEY_NAME"

if [ -z "${SAM_TRANSFORM_SSH_PRIVATE_KEY:-}" ]; then
    # Exit 0 rather than failing: a context without repository secrets should fail on the
    # dependency install itself, with this line in the log explaining why.
    echo "WARNING: SAM_TRANSFORM_SSH_PRIVATE_KEY is empty; $PRIVATE_REPO_PATH will not be cloneable." >&2
    exit 0
fi

mkdir -p "$HOME/.ssh"

# printf, not echo, so that escape sequences in the key material are preserved verbatim.
printf '%s\n' "$SAM_TRANSFORM_SSH_PRIVATE_KEY" > "$KEY_PATH"
chmod 600 "$KEY_PATH"

# Pin the key to github.com via ssh config rather than core.sshCommand: ssh expands "~"
# itself, which avoids handing a Git Bash style path to the Windows ssh client.
cat >> "$HOME/.ssh/config" <<EOF

Host github.com
    IdentityFile ~/.ssh/$KEY_NAME
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
EOF
chmod 600 "$HOME/.ssh/config"

# Best effort: pre-seed the host key so the first clone cannot stall on a prompt.
ssh-keyscan -t rsa,ecdsa,ed25519 github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null || true

# Scope the rewrite to the one private repository.
git config --global \
    "url.git@github.com:${PRIVATE_REPO_PATH}.insteadOf" \
    "https://github.com/${PRIVATE_REPO_PATH}"

echo "Configured SSH access for ${PRIVATE_REPO_PATH}"
