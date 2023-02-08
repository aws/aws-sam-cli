"""Module for storing information about existing workflows."""

from collections import namedtuple
from typing import List

CONFIG = namedtuple(
    "Capability",
    ["language", "dependency_manager", "application_framework", "manifest_name", "executable_search_paths"],
)

PYTHON_PIP_CONFIG = CONFIG(
    language="python",
    dependency_manager="pip",
    application_framework=None,
    manifest_name="requirements.txt",
    executable_search_paths=None,
)

NODEJS_NPM_CONFIG = CONFIG(
    language="nodejs",
    dependency_manager="npm",
    application_framework=None,
    manifest_name="package.json",
    executable_search_paths=None,
)

RUBY_BUNDLER_CONFIG = CONFIG(
    language="ruby",
    dependency_manager="bundler",
    application_framework=None,
    manifest_name="Gemfile",
    executable_search_paths=None,
)

JAVA_GRADLE_CONFIG = CONFIG(
    language="java",
    dependency_manager="gradle",
    application_framework=None,
    manifest_name="build.gradle",
    executable_search_paths=None,
)

JAVA_KOTLIN_GRADLE_CONFIG = CONFIG(
    language="java",
    dependency_manager="gradle",
    application_framework=None,
    manifest_name="build.gradle.kts",
    executable_search_paths=None,
)

JAVA_MAVEN_CONFIG = CONFIG(
    language="java",
    dependency_manager="maven",
    application_framework=None,
    manifest_name="pom.xml",
    executable_search_paths=None,
)

DOTNET_CLIPACKAGE_CONFIG = CONFIG(
    language="dotnet",
    dependency_manager="cli-package",
    application_framework=None,
    manifest_name=".csproj",
    executable_search_paths=None,
)

GO_MOD_CONFIG = CONFIG(
    language="go",
    dependency_manager="modules",
    application_framework=None,
    manifest_name="go.mod",
    executable_search_paths=None,
)

PROVIDED_MAKE_CONFIG = CONFIG(
    language="provided",
    dependency_manager=None,
    application_framework=None,
    manifest_name="Makefile",
    executable_search_paths=None,
)

NODEJS_NPM_ESBUILD_CONFIG = CONFIG(
    language="nodejs",
    dependency_manager="npm-esbuild",
    application_framework=None,
    manifest_name="package.json",
    executable_search_paths=None,
)

RUST_CARGO_LAMBDA_CONFIG = CONFIG(
    language="rust",
    dependency_manager="cargo",
    application_framework=None,
    manifest_name="Cargo.toml",
    executable_search_paths=None,
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
