"""
All-in-one metadata about runtimes
"""

import itertools
import os

import pathlib

from samcli.lib.build.workflow_config import PYTHON_PIP_CONFIG, RUBY_BUNDLER_CONFIG,\
    NODEJS_NPM_CONFIG, JAVA_GRADLE_CONFIG

_init_path = pathlib.Path(os.path.dirname(__file__)).parent
_templates = os.path.join(_init_path, 'init', 'templates')

# NOTE(TheSriram): Builder configs are only indicative of a builder config that is used for selecting a build workflow.
# The config mutates based on the workflow selector, so they  are not to be imported and used from the template mapping.
# They are an indication of metadata associated with a specific runtime.

RUNTIME_DEP_TEMPLATE_MAPPING = {
    "python": [
        {
            "runtimes": ["python2.7", "python3.6", "python3.7"],
            "dependency_manager": "pip",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-python"),
            "build": True,
            "builder_config": PYTHON_PIP_CONFIG
        }
    ],
    "ruby": [
        {
            "runtimes": ["ruby2.5"],
            "dependency_manager": "bundler",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-ruby"),
            "build": True,
            "builder_config": RUBY_BUNDLER_CONFIG
        }
    ],
    "nodejs": [
        {
            "runtimes": ["nodejs8.10"],
            "dependency_manager": "npm",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs"),
            "build": True,
            "builder_config": NODEJS_NPM_CONFIG
        },
        {
            "runtimes": ["nodejs6.10"],
            "dependency_manager": "npm",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-nodejs6"),
            "build": True,
            "builder_config": NODEJS_NPM_CONFIG
        },
    ],
    "dotnet": [
        {
            "runtimes": ["dotnetcore", "dotnetcore1.0", "dotnetcore2.0", "dotnetcore2.1"],
            "dependency_manager": "cli-package",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-dotnet"),
            "build": False,
            "builder_config": None
        },
    ],
    "go": [
        {
            "runtimes": ["go1.x"],
            "dependency_manager": None,
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-go"),
            "build": False,
            "builder_config": None
        }
    ],
    "java": [
        {
            "runtimes": ["java8"],
            "dependency_manager": "maven",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-maven"),
            "build": False,
            "builder_config": None
        },
        {
            "runtimes": ["java8"],
            "dependency_manager": "gradle",
            "init_location": os.path.join(_templates, "cookiecutter-aws-sam-hello-java-gradle"),
            "build": True,
            "builder_config": JAVA_GRADLE_CONFIG
        }
    ]
}

SUPPORTED_DEP_MANAGERS = set([c['dependency_manager'] for c in list(
    itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values()))) if c['dependency_manager']])
RUNTIMES = set(itertools.chain(*[c['runtimes'] for c in list(
    itertools.chain(*(RUNTIME_DEP_TEMPLATE_MAPPING.values())))]))
INIT_RUNTIMES = RUNTIMES.union(RUNTIME_DEP_TEMPLATE_MAPPING.keys())
