"""
All-in-one metadata about runtimes
"""

import itertools
import os
import pathlib

_init_path = str(pathlib.Path(os.path.dirname(__file__)).parent)
_templates = os.path.join(_init_path, "init", "templates")


# Note(TheSriram): The ordering of the runtimes list per language is based on the latest to oldest.
RUNTIME_DEP_TEMPLATE_MAPPING = {
    "python": [
        {
            "runtimes": ["python3.8", "python3.7", "python3.6", "python2.7"],
            "dependency_manager": "pip",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
            "build": True,
        }
    ],
    "ruby": [
        {
            "runtimes": ["ruby2.5", "ruby2.7"],
            "dependency_manager": "bundler",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-ruby"),
            "build": True,
        }
    ],
    "nodejs": [
        {
            "runtimes": ["nodejs12.x", "nodejs10.x"],
            "dependency_manager": "npm",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
            "build": True,
        }
    ],
    "dotnet": [
        {
            "runtimes": ["dotnetcore3.1", "dotnetcore2.1"],
            "dependency_manager": "cli-package",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
            "build": True,
        }
    ],
    "go": [
        {
            "runtimes": ["go1.x"],
            "dependency_manager": "mod",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-golang"),
            "build": False,
        }
    ],
    "java": [
        {
            "runtimes": ["java11", "java8", "java8.al2"],
            "dependency_manager": "maven",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
            "build": True,
        },
        {
            "runtimes": ["java11", "java8", "java8.al2"],
            "dependency_manager": "gradle",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-gradle"),
            "build": True,
        },
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
    c["dependency_manager"]
    for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))
    if c["dependency_manager"]
}

RUNTIMES = set(
    itertools.chain(*[c["runtimes"] for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))])
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

# Schemas Code lang is a MINIMUM supported version - this is why later Lambda runtimes can be mapped to earlier Schemas Code Languages
SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING = {
    "java8": "Java8",
    "java8.al2": "Java8",
    "java11": "Java8",
    "python3.7": "Python36",
    "python3.6": "Python36",
    "python3.8": "Python36",
}
