"""
Contains Builder Workflow Configs for different Runtimes
"""

from collections import namedtuple


CONFIG = namedtuple('Capability', ["language", "dependency_manager", "application_framework", "manifest_name"])

PYTHON_PIP_CONFIG = CONFIG(
                language="python",
                dependency_manager="pip",
                application_framework=None,
                manifest_name="requirements.txt")

NODEJS_NPM_CONFIG = CONFIG(
                language="nodejs",
                dependency_manager="npm",
                application_framework=None,
                manifest_name="package.json")

RUBY_BUNDLER_CONFIG = CONFIG(
                language="ruby",
                dependency_manager="bundler",
                application_framework=None,
                manifest_name="Gemfile")


class UnsupportedRuntimeException(Exception):
    pass


def get_workflow_config(runtime):
    """
    Get a workflow config that corresponds to the runtime provided

    Parameters
    ----------
    runtime str
        The runtime of the config

    Returns
    -------
    namedtuple(Capability)
        namedtuple that represents the Builder Workflow Config
    """

    workflow_config_by_runtime = {
        "python2.7": PYTHON_PIP_CONFIG,
        "python3.6": PYTHON_PIP_CONFIG,
        "python3.7": PYTHON_PIP_CONFIG,
        "nodejs4.3": NODEJS_NPM_CONFIG,
        "nodejs6.10": NODEJS_NPM_CONFIG,
        "nodejs8.10": NODEJS_NPM_CONFIG,
        "ruby2.5": RUBY_BUNDLER_CONFIG
    }

    try:
        return workflow_config_by_runtime[runtime]
    except KeyError:
        raise UnsupportedRuntimeException("'{}' runtime is not supported".format(runtime))
