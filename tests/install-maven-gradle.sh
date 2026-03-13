#!/bin/bash
# Install latest stable Maven and Gradle for SAM CLI integration tests.
set -euo pipefail

echo "=== Before install ==="
mvn --version 2>&1 || echo "Maven: not installed"
gradle --version 2>&1 || echo "Gradle: not installed"

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  choco install maven gradle -y
  # Refresh PATH for current session
  eval "$(powershell.exe -Command '[Environment]::GetEnvironmentVariable("Path","Machine")' | tr ';' '\n' | sed 's|\\|/|g' | while read -r p; do echo "export PATH=\"$p:\$PATH\""; done)"
else
  sudo apt-get update -qq
  sudo apt-get install -y -qq maven gradle
fi

echo "=== After install ==="
mvn --version 2>&1 || echo "Maven: not installed"
gradle --version 2>&1 || echo "Gradle: not installed"
