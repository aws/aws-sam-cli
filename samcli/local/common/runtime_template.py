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


def get_local_lambda_images_location(mapping, runtime):
    dir_name = os.path.basename(mapping["init_location"])
    if dir_name.endswith("-lambda-image"):
        return os.path.join(_lambda_images_templates, runtime, dir_name)

    return os.path.join(_lambda_images_templates, runtime, dir_name + "-lambda-image")


RUNTIME_TO_DEPENDENCY_MANAGERS = {
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
# Order here should be a the group of the latest versions of runtimes followed by runtime groups
INIT_RUNTIMES = [
    # latest of each runtime version
    "nodejs14.x",
    "python3.8",
    "ruby2.7",
    "go1.x",
    "java11",
    "dotnetcore3.1",
    # older nodejs runtimes
    "nodejs12.x",
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

LAMBDA_IMAGES_RUNTIMES = [
    "amazon/nodejs14.x-base",
    "amazon/nodejs12.x-base",
    "amazon/nodejs10.x-base",
    "amazon/python3.8-base",
    "amazon/python3.7-base",
    "amazon/python3.6-base",
    "amazon/python2.7-base",
    "amazon/ruby2.7-base",
    "amazon/ruby2.5-base",
    "amazon/go1.x-base",
    "amazon/java11-base",
    "amazon/java8.al2-base",
    "amazon/java8-base",
    "amazon/dotnet5.0-base",
    "amazon/dotnetcore3.1-base",
    "amazon/dotnetcore2.1-base",
]

# Schemas Code lang is a MINIMUM supported version
# - this is why later Lambda runtimes can be mapped to earlier Schemas Code Languages
SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING = {
    "java8": "Java8",
    "java8.al2": "Java8",
    "java11": "Java8",
    "python3.7": "Python36",
    "python3.6": "Python36",
    "python3.8": "Python36",
}
