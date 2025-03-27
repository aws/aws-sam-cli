"""
All-in-one metadata about runtimes
"""

import itertools
import os
import pathlib
import re
from typing import List

_init_path = str(pathlib.Path(os.path.dirname(__file__)).parent.parent)
_templates = os.path.join(_init_path, "lib", "init", "templates")
_lambda_images_templates = os.path.join(_init_path, "lib", "init", "image_templates")

# Note(TheSriram): The ordering of the runtimes list per language is based on the latest to oldest.
RUNTIME_DEP_TEMPLATE_MAPPING = {
    "python": [
        {
            "runtimes": ["python3.13", "python3.12", "python3.11", "python3.10", "python3.9", "python3.8"],
            "dependency_manager": "pip",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
            "build": True,
        }
    ],
    "ruby": [
        {
            "runtimes": ["ruby3.4", "ruby3.3", "ruby3.2"],
            "dependency_manager": "bundler",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-ruby"),
            "build": True,
        }
    ],
    "nodejs": [
        {
            "runtimes": ["nodejs22.x", "nodejs20.x", "nodejs18.x", "nodejs16.x"],
            "dependency_manager": "npm",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
            "build": True,
        }
    ],
    "dotnet": [
        {
            "runtimes": ["dotnet8", "dotnet6"],
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
            "runtimes": ["java11", "java8.al2", "java17", "java21"],
            "dependency_manager": "maven",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
            "build": True,
        },
        {
            "runtimes": ["java11", "java8.al2", "java17", "java21"],
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


SUPPORTED_DEP_MANAGERS: List[str] = sorted(
    list(
        set(
            {
                c.get("dependency_manager")  # type: ignore
                for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))
                if c.get("dependency_manager")
            }
        )
    )
)

# When adding new Lambda runtimes, please update SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING
# Runtimes are ordered in alphabetical fashion with reverse version order (latest versions first)
INIT_RUNTIMES = [
    # dotnet runtimes in descending order
    "dotnet8",
    "dotnet6",
    # go runtimes in descending order
    "go1.x",
    # java runtimes in descending order
    "java21",
    "java17",
    "java11",
    "java8.al2",
    # nodejs runtimes in descending order
    "nodejs22.x",
    "nodejs20.x",
    "nodejs18.x",
    "nodejs16.x",
    # custom runtime in descending order
    "provided.al2023",
    "provided.al2",
    "provided",
    # python runtimes in descending order
    "python3.13",
    "python3.12",
    "python3.11",
    "python3.10",
    "python3.9",
    "python3.8",
    # ruby runtimes in descending order
    "ruby3.4",
    "ruby3.3",
    "ruby3.2",
]


LAMBDA_IMAGES_RUNTIMES_MAP = {
    "dotnet8": "amazon/dotnet8-base",
    "dotnet6": "amazon/dotnet6-base",
    "go1.x": "amazon/go1.x-base",
    "go (provided.al2)": "amazon/go-provided.al2-base",
    "go (provided.al2023)": "amazon/go-provided.al2023-base",
    "java21": "amazon/java21-base",
    "java17": "amazon/java17-base",
    "java11": "amazon/java11-base",
    "java8.al2": "amazon/java8.al2-base",
    "nodejs22.x": "amazon/nodejs22.x-base",
    "nodejs20.x": "amazon/nodejs20.x-base",
    "nodejs18.x": "amazon/nodejs18.x-base",
    "nodejs16.x": "amazon/nodejs16.x-base",
    "python3.13": "amazon/python3.13-base",
    "python3.12": "amazon/python3.12-base",
    "python3.11": "amazon/python3.11-base",
    "python3.10": "amazon/python3.10-base",
    "python3.9": "amazon/python3.9-base",
    "python3.8": "amazon/python3.8-base",
    "ruby3.4": "amazon/ruby3.4-base",
    "ruby3.3": "amazon/ruby3.3-base",
    "ruby3.2": "amazon/ruby3.2-base",
}

LAMBDA_IMAGES_RUNTIMES: List = sorted(list(set(LAMBDA_IMAGES_RUNTIMES_MAP.values())))

# Schemas Code lang is a MINIMUM supported version
# - this is why later Lambda runtimes can be mapped to earlier Schemas Code Languages
# event schema registry supports only java8, python3.6, dotnet6, and Go1 for code binding
SAM_RUNTIME_TO_SCHEMAS_CODE_LANG_MAPPING = {
    "java8.al2": "Java8",
    "java11": "Java8",
    "java17": "Java8",
    "java21": "Java8",
    "python3.8": "Python36",
    "python3.9": "Python36",
    "python3.10": "Python36",
    "python3.11": "Python36",
    "python3.12": "Python36",
    "python3.13": "Python36",
    "dotnet6": "dotnet6",
    "dotnet8": "dotnet6",
    "go1.x": "Go1",
    "provided.al2": "Go1",
}

PROVIDED_RUNTIMES = ["provided.al2023", "provided.al2", "provided"]


def is_custom_runtime(runtime):
    """
    validated if a runtime is custom or not
    Parameters
    ----------
    runtime : str
        runtime to be
    Returns
    -------
    _type_
        _description_
    """
    if not runtime:
        return False
    provided_runtime = get_provided_runtime_from_custom_runtime(runtime)
    return runtime in PROVIDED_RUNTIMES or bool(provided_runtime in PROVIDED_RUNTIMES)


def get_provided_runtime_from_custom_runtime(runtime):
    """
    Gets the base lambda runtime for which a custom runtime is based on
    Example:
    rust (provided.al2) --> provided.al2
    java11 --> None

    Parameters
    ----------
    runtime : str
        Custom runtime or Lambda runtime

    Returns
    -------
    str
        returns the base lambda runtime for which a custom runtime is based on
    """
    base_runtime_list = re.findall(r"\(([^()]+)\)", runtime)
    return base_runtime_list[0] if base_runtime_list else None
