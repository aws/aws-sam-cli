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
            "runtimes": ["ruby2.5"],
            "dependency_manager": "bundler",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-ruby"),
            "build": True,
        }
    ],
    "nodejs": [
        {
            "runtimes": ["nodejs12.x", "nodejs10.x", "nodejs8.10"],
            "dependency_manager": "npm",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
            "build": True,
        },
        {
            "runtimes": ["nodejs6.10"],
            "dependency_manager": "npm",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs6"),
            "build": True,
        },
    ],
    "dotnet": [
        {
            "runtimes": ["dotnetcore2.1", "dotnetcore2.0", "dotnetcore1.0"],
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
            "runtimes": ["java11", "java8"],
            "dependency_manager": "maven",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
            "build": True,
        },
        {
            "runtimes": ["java11", "java8"],
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
    "nodejs12.x": ["npm"],
    "nodejs10.x": ["npm"],
    "nodejs8.10": ["npm"],
    "nodejs6.10": ["npm"],
    "dotnetcore2.1": ["cli-package"],
    "dotnetcore2.0": ["cli-package"],
    "dotnetcore1.0": ["cli-package"],
    "go1.x": ["mod"],
    "java8": ["maven", "gradle"],
    "java11": ["maven", "gradle"],
}

SUPPORTED_DEP_MANAGERS = {
    c["dependency_manager"]
    for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))
    if c["dependency_manager"]
}

RUNTIMES = set(
    itertools.chain(*[c["runtimes"] for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))])
)

# Order here should be a the group of the latest versions of runtimes followed by runtime groups
INIT_RUNTIMES = [
    # latest of each runtime version
    "nodejs12.x",
    "python3.8",
    "ruby2.5",
    "go1.x",
    "java11",
    "dotnetcore2.1",
    # older nodejs runtimes
    "nodejs10.x",
    "nodejs8.10",
    "nodejs6.10",
    # older python runtimes
    "python3.7",
    "python3.6",
    "python2.7",
    # older ruby runtimes
    # older java runtimes
    "java8",
    # older dotnetcore runtimes
    "dotnetcore2.0",
    "dotnetcore1.0",
]
