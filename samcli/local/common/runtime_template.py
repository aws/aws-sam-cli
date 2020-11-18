"""
All-in-one metadata about runtimes
"""

import itertools
import os
import pathlib
from dataclasses import dataclass
from typing import List, Dict

_init_path = str(pathlib.Path(os.path.dirname(__file__)).parent)
_templates = os.path.join(_init_path, "init", "templates")


@dataclass
class RuntimeDepInfo:
    runtimes: List[str]
    dependency_manager: str
    init_location: str
    build: bool


# Note(TheSriram): The ordering of the runtimes list per language is based on the latest to oldest.
RUNTIME_DEP_TEMPLATE_MAPPING: Dict[str, List[RuntimeDepInfo]] = {
    "python": [
        RuntimeDepInfo(
            ["python3.8", "python3.7", "python3.6", "python2.7"],
            "pip",
            os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
            True,
        )
    ],
    "ruby": [
        RuntimeDepInfo(
            ["ruby2.5", "ruby2.7"],
            "bundler",
            os.path.join(_templates, "cookiecutter-aws-sam-hello-ruby"),
            True,
        )
    ],
    "nodejs": [
        RuntimeDepInfo(
            ["nodejs12.x", "nodejs10.x"],
            "npm",
            os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
            True,
        )
    ],
    "dotnet": [
        RuntimeDepInfo(
            ["dotnetcore3.1", "dotnetcore2.1"],
            "cli-package",
            os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
            True,
        )
    ],
    "go": [
        RuntimeDepInfo(
            ["go1.x"],
            "mod",
            os.path.join(_templates, "cookiecutter-aws-sam-hello-golang"),
            False,
        )
    ],
    "java": [
        RuntimeDepInfo(
            ["java11", "java8", "java8.al2"],
            "maven",
            os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
            True,
        ),
        RuntimeDepInfo(
            ["java11", "java8", "java8.al2"],
            "gradle",
            os.path.join(_templates, "cookiecutter-aws-sam-hello-java-gradle"),
            True,
        ),
    ],
}

RUNTIME_TO_DEPENDENCY_MANAGERS = {
    "python3.8": ["pip"],
    "python3.7": ["pip"],
    "python3.6": ["pip"],
    "python2.7": ["pip"],
    "ruby2.5": ["bundler"],
    "ruby2.7": ["bundler"],
    "nodejs12.x": ["npm"],
    "nodejs10.x": ["npm"],
    "dotnetcore3.1": ["cli-package"],
    "dotnetcore2.1": ["cli-package"],
    "go1.x": ["mod"],
    "java8": ["maven", "gradle"],
    "java11": ["maven", "gradle"],
    "java8.al2": ["maven", "gradle"],
}


SUPPORTED_DEP_MANAGERS = {
    c.dependency_manager
    for c in list(itertools.chain.from_iterable(RUNTIME_DEP_TEMPLATE_MAPPING.values()))
    if c.dependency_manager
}

RUNTIMES = set(
    itertools.chain.from_iterable(
        [c.runtimes for c in list(itertools.chain.from_iterable(RUNTIME_DEP_TEMPLATE_MAPPING.values()))]
    )
)

# When adding new Lambda runtimes, please update SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING
# Order here should be a the group of the latest versions of runtimes followed by runtime groups
INIT_RUNTIMES = [
    # latest of each runtime version
    "nodejs12.x",
    "python3.8",
    "ruby2.7",
    "go1.x",
    "java11",
    "dotnetcore3.1",
    # older nodejs runtimes
    "nodejs10.x",
    # older python runtimes
    "python3.7",
    "python3.6",
    "python2.7",
    # older ruby runtimes
    "ruby2.5",
    # older java runtimes
    "java8.al2",
    "java8",
    # older dotnetcore runtimes
    "dotnetcore2.1",
]

# Schemas Code lang is a MINIMUM supported version
# this is why later Lambda runtimes can be mapped to earlier Schemas Code Languages
SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING = {
    "java8": "Java8",
    "java8.al2": "Java8",
    "java11": "Java8",
    "python3.7": "Python36",
    "python3.6": "Python36",
    "python3.8": "Python36",
}
