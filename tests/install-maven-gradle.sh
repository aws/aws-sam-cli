#!/bin/bash
# Install Maven 3.9.13 and Gradle 9.3.1 for SAM CLI integration tests.
# Supports both Linux and Windows (Git Bash on GitHub Actions).
set -euo pipefail

MAVEN_VERSION="3.9.13"
GRADLE_VERSION="9.3.1"

# Check if correct versions are already installed
MAVEN_INSTALLED=$(mvn --version 2>/dev/null | head -1 | grep -o "${MAVEN_VERSION}" || true)
GRADLE_INSTALLED=$(gradle --version 2>/dev/null | grep "Gradle ${GRADLE_VERSION}" || true)

if [[ -n "$MAVEN_INSTALLED" && -n "$GRADLE_INSTALLED" ]]; then
  echo "Maven ${MAVEN_VERSION} and Gradle ${GRADLE_VERSION} are already installed, skipping."
  mvn --version
  gradle --version
  exit 0
fi

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  echo "=== Installing Maven ${MAVEN_VERSION} and Gradle ${GRADLE_VERSION} on Windows via choco ==="
  [[ -z "$MAVEN_INSTALLED" ]] && choco install maven --version="${MAVEN_VERSION}" -y --allow-downgrade || true
  [[ -z "$GRADLE_INSTALLED" ]] && choco install gradle --version="${GRADLE_VERSION}" -y --allow-downgrade || true
else
  echo "=== Installing Maven ${MAVEN_VERSION} and Gradle ${GRADLE_VERSION} on Linux ==="
  sudo apt-get remove -y maven || true

  wget -q "https://dlcdn.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.zip" -P /tmp || true
  sudo unzip -o -q /tmp/apache-maven-*.zip -d /opt/mvn || true

  wget -q "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -P /tmp || true
  sudo unzip -o -q /tmp/gradle-*.zip -d /opt/gradle || true

  sudo ln -sf "/opt/mvn/apache-maven-${MAVEN_VERSION}/bin/mvn" /usr/local/bin/mvn || true
  sudo ln -sf "/opt/gradle/gradle-${GRADLE_VERSION}/bin/gradle" /usr/local/bin/gradle || true

  echo "/opt/mvn/apache-maven-${MAVEN_VERSION}/bin" >> "$GITHUB_PATH" || true
  echo "/opt/gradle/gradle-${GRADLE_VERSION}/bin" >> "$GITHUB_PATH" || true
  echo "MAVEN_HOME=/opt/mvn/apache-maven-${MAVEN_VERSION}" >> "$GITHUB_ENV" || true

  export PATH="/opt/mvn/apache-maven-${MAVEN_VERSION}/bin:/opt/gradle/gradle-${GRADLE_VERSION}/bin:$PATH"
fi

# Verify installations — warn on version mismatch, fail only if binary is missing
if ! command -v mvn &>/dev/null; then
  echo "ERROR: mvn not found after installation attempt."
  exit 1
fi
if ! mvn --version 2>/dev/null | head -1 | grep -q "${MAVEN_VERSION}"; then
  echo "WARNING: Expected Maven ${MAVEN_VERSION} but found:"
  mvn --version || true
fi

if ! command -v gradle &>/dev/null; then
  echo "ERROR: gradle not found after installation attempt."
  exit 1
fi
if ! gradle --version 2>/dev/null | grep -q "Gradle ${GRADLE_VERSION}"; then
  echo "WARNING: Expected Gradle ${GRADLE_VERSION} but found:"
  gradle --version || true
fi

echo "=== Maven and Gradle installation complete ==="
