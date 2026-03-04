#!/bin/bash
# Install Maven 3.9.12 and Gradle 9.2.0 for SAM CLI integration tests.
# Supports both Linux and Windows (Git Bash on GitHub Actions).
set -euo pipefail

MAVEN_VERSION="3.9.12"
GRADLE_VERSION="9.3.1"

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  echo "=== Installing Maven ${MAVEN_VERSION} and Gradle ${GRADLE_VERSION} on Windows via choco ==="
  choco install maven --version="${MAVEN_VERSION}" -y --allow-downgrade
  choco install gradle --version="${GRADLE_VERSION}" -y --allow-downgrade
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

mvn --version
gradle --version
echo "=== Maven and Gradle installation complete ==="
