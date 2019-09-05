"""
All-in-one metadata about runtimes
"""

import itertools
import os

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

_init_path = str(pathlib.Path(os.path.dirname(__file__)).parent)
_templates = os.path.join(_init_path, "init", "templates")


# Note(TheSriram): The ordering of the runtimes list per language is based on the latest to oldest.
RUNTIME_DEP_TEMPLATE_MAPPING = {
    "python": [
        {
            "runtimes": ["python3.7", "python3.6", "python2.7"],
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
            "runtimes": ["nodejs10.x", "nodejs8.10"],
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
            "runtimes": ["dotnetcore2.1", "dotnetcore2.0", "dotnetcore1.0", "dotnetcore"],
            "dependency_manager": "cli-package",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
            "build": True,
        }
    ],
    "go": [
        {
            "runtimes": ["go1.x"],
            "dependency_manager": None,
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-golang"),
            "build": False,
        }
    ],
    "java": [
        {
            "runtimes": ["java8"],
            "dependency_manager": "maven",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
            "build": True,
        },
        {
            "runtimes": ["java8"],
            "dependency_manager": "gradle",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-gradle"),
            "build": True,
        },
    ],
}

SUPPORTED_DEP_MANAGERS = set(
    [
        c["dependency_manager"]
        for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))
        if c["dependency_manager"]
    ]
)
RUNTIMES = set(
    itertools.chain(*[c["runtimes"] for c in list(itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))])
)
INIT_RUNTIMES = RUNTIMES.union(RUNTIME_DEP_TEMPLATE_MAPPING.keys())

# NOTE(TheSriram): Default Runtime Choice when runtime is not chosen
DEFAULT_RUNTIME = RUNTIME_DEP_TEMPLATE_MAPPING["nodejs"][0]["runtimes"][0]
