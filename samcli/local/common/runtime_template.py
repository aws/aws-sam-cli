"""
All-in-one metadata about runtimes
"""

import itertools
import os
import pathlib
from typing import Set

_init_path = str(pathlib.Path(os.path.dirname(__file__)).parent.parent)
_templates = os.path.join(_init_path, "lib", "init", "templates")
_lambda_images_templates = os.path.join(_init_path, "lib", "init", "image_templates")

# Note(TheSriram): The ordering of the runtimes list per language is based on the latest to oldest.
RUNTIME_DEP_TEMPLATE_MAPPING = {
    "python": [
        {
            "runtimes": ["python3.9", "python3.8", "python3.7", "python3.6", "python2.7"],
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
            "runtimes": ["nodejs14.x", "nodejs12.x", "nodejs10.x"],
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


def get_local_manifest_path():
    return pathlib.Path(_init_path, "lib", "init", "local_manifest.json")


def get_local_lambda_images_location(mapping, runtime):
    dir_name = os.path.basename(mapping["init_location"])
    if dir_name.endswith("-lambda-image"):
        return os.path.join(_lambda_images_templates, runtime, dir_name)

    return os.path.join(_lambda_images_templates, runtime, dir_name + "-lambda-image")


RUNTIME_TO_DEPENDENCY_MANAGERS = {
    "python3.9": ["pip"],
    "python3.8": ["pip"],
    "python3.7": ["pip"],
    "python3.6": ["pip"],
    "python2.7": ["pip"],
    "ruby2.5": ["bundler"],
    "ruby2.7": ["bundler"],
    "nodejs14.x": ["npm"],
    "nodejs12.x": ["npm"],
    "nodejs10.x": ["npm"],
    "dotnetcore3.1": ["cli-package"],
    "dotnetcore2.1": ["cli-package"],
    "go1.x": ["mod"],
    "java8": ["maven", "gradle"],
    "java11": ["maven", "gradle"],
    "java8.al2": ["maven", "gradle"],
}

SUPPORTED_DEP_MANAGERS: Set[str] = {
    c["dependency_manager"]  # type: ignore
    for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))
    if c["dependency_manager"]
}

RUNTIMES: Set[str] = set(
    itertools.chain(
        *[c["runtimes"] for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))]  # type: ignore
    )
)

# When adding new Lambda runtimes, please update SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING
# Runtimes are ordered in alphabetical fashion with reverse version order (latest versions first)
INIT_RUNTIMES = [
    # dotnetcore runtimes in descending order
    "dotnet5.0",
    "dotnetcore3.1",
    "dotnetcore2.1",
    "go1.x",
    # java runtimes in descending order
    "java11",
    "java8.al2",
    "java8",
    # nodejs runtimes in descending order
    "nodejs14.x",
    "nodejs12.x",
    "nodejs10.x",
    # python runtimes in descending order
    "python3.9",
    "python3.8",
    "python3.7",
    "python3.6",
    "python2.7",
    # ruby runtimes in descending order
    "ruby2.7",
    "ruby2.5",
]


LAMBDA_IMAGES_RUNTIMES_MAP = {
    "dotnet5.0": "amazon/dotnet5.0-base",
    "dotnetcore3.1": "amazon/dotnetcore3.1-base",
    "dotnetcore2.1": "amazon/dotnetcore2.1-base",
    "go1.x": "amazon/go1.x-base",
    "java11": "amazon/java11-base",
    "java8.al2": "amazon/java8.al2-base",
    "java8": "amazon/java8-base",
    "nodejs14.x": "amazon/nodejs14.x-base",
    "nodejs12.x": "amazon/nodejs12.x-base",
    "nodejs10.x": "amazon/nodejs10.x-base",
    "python3.9": "amazon/python3.9-base",
    "python3.8": "amazon/python3.8-base",
    "python3.7": "amazon/python3.7-base",
    "python3.6": "amazon/python3.6-base",
    "python2.7": "amazon/python2.7-base",
    "ruby2.7": "amazon/ruby2.7-base",
    "ruby2.5": "amazon/ruby2.5-base",
}

LAMBDA_IMAGES_RUNTIMES = LAMBDA_IMAGES_RUNTIMES_MAP.values()

# Schemas Code lang is a MINIMUM supported version
# - this is why later Lambda runtimes can be mapped to earlier Schemas Code Languages
SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING = {
    "java8": "Java8",
    "java8.al2": "Java8",
    "java11": "Java8",
    "python3.7": "Python36",
    "python3.6": "Python36",
    "python3.8": "Python36",
    "python3.9": "Python36",
}
