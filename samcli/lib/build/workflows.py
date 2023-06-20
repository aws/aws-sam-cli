"""Module for storing information about existing workflows."""

from collections import namedtuple
from typing import List

CONFIG = namedtuple(
    "CONFIG",
    [
        "language",
        "dependency_manager",
        "application_framework",
        "manifest_name",
        "executable_search_paths",
        "must_mount_with_write_in_container",
    ],
)

PYTHON_PIP_CONFIG = CONFIG(
    language="python",
    dependency_manager="pip",
    application_framework=None,
    manifest_name="requirements.txt",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

NODEJS_NPM_CONFIG = CONFIG(
    language="nodejs",
    dependency_manager="npm",
    application_framework=None,
    manifest_name="package.json",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

RUBY_BUNDLER_CONFIG = CONFIG(
    language="ruby",
    dependency_manager="bundler",
    application_framework=None,
    manifest_name="Gemfile",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

JAVA_GRADLE_CONFIG = CONFIG(
    language="java",
    dependency_manager="gradle",
    application_framework=None,
    manifest_name="build.gradle",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

JAVA_KOTLIN_GRADLE_CONFIG = CONFIG(
    language="java",
    dependency_manager="gradle",
    application_framework=None,
    manifest_name="build.gradle.kts",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

JAVA_MAVEN_CONFIG = CONFIG(
    language="java",
    dependency_manager="maven",
    application_framework=None,
    manifest_name="pom.xml",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

# dotnet must mount with write for container builds because it outputs to source code directory by default
DOTNET_CLIPACKAGE_CONFIG = CONFIG(
    language="dotnet",
    dependency_manager="cli-package",
    application_framework=None,
    manifest_name=".csproj",
    executable_search_paths=None,
    must_mount_with_write_in_container=True,
)

GO_MOD_CONFIG = CONFIG(
    language="go",
    dependency_manager="modules",
    application_framework=None,
    manifest_name="go.mod",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

PROVIDED_MAKE_CONFIG = CONFIG(
    language="provided",
    dependency_manager=None,
    application_framework=None,
    manifest_name="Makefile",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

NODEJS_NPM_ESBUILD_CONFIG = CONFIG(
    language="nodejs",
    dependency_manager="npm-esbuild",
    application_framework=None,
    manifest_name="package.json",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

RUST_CARGO_LAMBDA_CONFIG = CONFIG(
    language="rust",
    dependency_manager="cargo",
    application_framework=None,
    manifest_name="Cargo.toml",
    executable_search_paths=None,
    must_mount_with_write_in_container=False,
)

ALL_CONFIGS: List[CONFIG] = [
    PYTHON_PIP_CONFIG,
    NODEJS_NPM_CONFIG,
    RUBY_BUNDLER_CONFIG,
    JAVA_GRADLE_CONFIG,
    JAVA_KOTLIN_GRADLE_CONFIG,
    JAVA_MAVEN_CONFIG,
    DOTNET_CLIPACKAGE_CONFIG,
    GO_MOD_CONFIG,
    PROVIDED_MAKE_CONFIG,
    NODEJS_NPM_ESBUILD_CONFIG,
    RUST_CARGO_LAMBDA_CONFIG,
]
