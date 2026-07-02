#!/bin/bash
# Install latest stable Maven 3.x and Gradle for SAM CLI integration tests.
# Auto-detects latest versions from official APIs.
# Skips install if pre-installed versions meet minimums.
set -euo pipefail

MIN_MAVEN="3.9.12"
MIN_GRADLE="9.2.0"

version_gte() { printf '%s\n%s' "$2" "$1" | sort -V -C; }
get_maven_ver() { mvn --version 2>/dev/null | head -1 | sed -n 's/.*Maven \([0-9.]*\).*/\1/p' || true; }
get_gradle_ver() { gradle --version 2>/dev/null | sed -n 's/.*Gradle \([0-9.]*\).*/\1/p' || true; }

MVN_VER=$(get_maven_ver)
GRADLE_VER=$(get_gradle_ver)
echo "=== Current: Maven=${MVN_VER:-none} Gradle=${GRADLE_VER:-none} ==="

NEED_MAVEN=true; NEED_GRADLE=true
[[ -n "$MVN_VER" ]] && version_gte "$MVN_VER" "$MIN_MAVEN" && NEED_MAVEN=false
[[ -n "$GRADLE_VER" ]] && version_gte "$GRADLE_VER" "$MIN_GRADLE" && NEED_GRADLE=false

if ! $NEED_MAVEN && ! $NEED_GRADLE; then
  echo "Versions sufficient, skipping install."
  exit 0
fi

resolve_maven_version() {
  curl -sfL "https://repo1.maven.org/maven2/org/apache/maven/apache-maven/maven-metadata.xml" \
    | sed -n 's/.*<version>3\.9\.\([0-9]*\)<.*/\1/p' | sort -n | tail -1 | xargs -I{} echo "3.9.{}"
}

resolve_gradle_version() {
  curl -sfL "https://services.gradle.org/versions/current" | sed -n 's/.*"version"\s*:\s*"\([^"]*\)".*/\1/p'
}

if [[ "${RUNNER_OS:-}" == "Windows" ]]; then
  $NEED_MAVEN && choco install maven -y
  $NEED_GRADLE && choco install gradle -y
  CHOCO_BASE="C:/ProgramData/chocolatey/lib"
  MVN_BIN=$(find "$CHOCO_BASE/maven" -name "mvn.cmd" -print -quit 2>/dev/null | xargs dirname || true)
  GRADLE_BIN=$(find "$CHOCO_BASE/gradle" -name "gradle.bat" -print -quit 2>/dev/null | xargs dirname || true)
  [[ -n "$MVN_BIN" ]] && { export PATH="$MVN_BIN:$PATH"; echo "$MVN_BIN" >> "$GITHUB_PATH"; }
  [[ -n "$GRADLE_BIN" ]] && { export PATH="$GRADLE_BIN:$PATH"; echo "$GRADLE_BIN" >> "$GITHUB_PATH"; }
else
  sudo apt-get remove -y maven 2>/dev/null || true

  if $NEED_MAVEN; then
    MAVEN_VERSION=$(resolve_maven_version)
    echo "Installing Maven ${MAVEN_VERSION}..."
    wget -q "https://dlcdn.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" -O /tmp/maven.tar.gz
    sudo tar -xzf /tmp/maven.tar.gz -C /opt
    sudo ln -sf "/opt/apache-maven-${MAVEN_VERSION}/bin/mvn" /usr/local/bin/mvn
    echo "MAVEN_HOME=/opt/apache-maven-${MAVEN_VERSION}" >> "$GITHUB_ENV"
  fi

  if $NEED_GRADLE; then
    GRADLE_VERSION=$(resolve_gradle_version)
    echo "Installing Gradle ${GRADLE_VERSION}..."
    wget -q "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -O /tmp/gradle.zip
    sudo unzip -o -q /tmp/gradle.zip -d /opt
    sudo ln -sf "/opt/gradle-${GRADLE_VERSION}/bin/gradle" /usr/local/bin/gradle
  fi
fi

echo "=== Installed: Maven=$(get_maven_ver) Gradle=$(get_gradle_ver) ==="
