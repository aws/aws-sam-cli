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
  [[ -z "$MAVEN_INSTALLED" ]] && choco install maven --version="${MAVEN_VERSION}" -y --allow-downgrade
  [[ -z "$GRADLE_INSTALLED" ]] && choco install gradle --version="${GRADLE_VERSION}" -y --allow-downgrade

  # Chocolatey updates the system PATH in the registry but the current bash session
  # doesn't see it. Explicitly add the known install paths so mvn/gradle are available
  # in this session and in subsequent workflow steps.
  CHOCO_MAVEN_BIN="C:/ProgramData/chocolatey/lib/maven/apache-maven-${MAVEN_VERSION}/bin"
  CHOCO_GRADLE_BIN="C:/ProgramData/chocolatey/lib/gradle/gradle-${GRADLE_VERSION}/bin"
  export PATH="${CHOCO_MAVEN_BIN}:${CHOCO_GRADLE_BIN}:${PATH}"
  echo "${CHOCO_MAVEN_BIN}" >> "$GITHUB_PATH"
  echo "${CHOCO_GRADLE_BIN}" >> "$GITHUB_PATH"
else
  echo "=== Installing Maven ${MAVEN_VERSION} and Gradle ${GRADLE_VERSION} on Linux ==="
  sudo apt-get remove -y maven || true

  wget -q "https://dlcdn.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.zip" -P /tmp
  sudo unzip -o -q /tmp/apache-maven-*.zip -d /opt/mvn

  wget -q "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -P /tmp
  sudo unzip -o -q /tmp/gradle-*.zip -d /opt/gradle

  sudo ln -sf "/opt/mvn/apache-maven-${MAVEN_VERSION}/bin/mvn" /usr/local/bin/mvn
  sudo ln -sf "/opt/gradle/gradle-${GRADLE_VERSION}/bin/gradle" /usr/local/bin/gradle

  echo "/opt/mvn/apache-maven-${MAVEN_VERSION}/bin" >> "$GITHUB_PATH"
  echo "/opt/gradle/gradle-${GRADLE_VERSION}/bin" >> "$GITHUB_PATH"
  echo "MAVEN_HOME=/opt/mvn/apache-maven-${MAVEN_VERSION}" >> "$GITHUB_ENV"

  export PATH="/opt/mvn/apache-maven-${MAVEN_VERSION}/bin:/opt/gradle/gradle-${GRADLE_VERSION}/bin:$PATH"
fi

mvn --version || echo "WARNING: mvn --version failed"
gradle --version || echo "WARNING: gradle --version failed"
echo "=== Maven and Gradle installation complete ==="
