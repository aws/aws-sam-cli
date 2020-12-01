"""
Contains Builder Workflow Configs for different Runtimes
"""

import os
import logging
from collections import namedtuple

LOG = logging.getLogger(__name__)

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


class UnsupportedRuntimeException(Exception):
    pass


class UnsupportedBuilderException(Exception):
    pass


def get_selector(selector_list, identifiers, specified_workflow=None):
    """
    Determine the correct workflow selector from a list of selectors, series of identifiers and user specified workflow if defined.

    Parameters
    ----------
    selector_list list
        List of dictionaries, where the value of all dictionaries are workflow selectors.
    identifiers list
        List of identifiers specified in order of precedence that are to be looked up in selector_list.
    specified_workflow str
        User specified workflow for build.

    Returns
    -------
    selector(BasicWorkflowSelector)
        selector object which can specify a workflow configuration that can be passed to `aws-lambda-builders`

    """

    # Create a combined view of all the selectors
    all_selectors = {}
    for selector in selector_list:
        all_selectors = {**all_selectors, **selector}

    # Check for specified workflow being supported at all and if it's not, raise an UnsupportedBuilderException.
    if specified_workflow and specified_workflow not in all_selectors:
        raise UnsupportedBuilderException("'{}' does not have a supported builder".format(specified_workflow))

    # Loop through all identifers to gather list of selectors with potential matches.
    selectors = [all_selectors.get(identifier, None) for identifier in identifiers]

    # Intialize a `None` selector.
    selector = None

    try:
        # Find first non-None selector.
        # Return the first selector with a match.
        selector = next(_selector for _selector in selectors if _selector)
    except StopIteration:
        pass

    return selector


def get_layer_subfolder(build_workflow):
    subfolders_by_runtime = {
        "python2.7": "python",
        "python3.6": "python",
        "python3.7": "python",
        "python3.8": "python",
        "nodejs4.3": "nodejs",
        "nodejs6.10": "nodejs",
        "nodejs8.10": "nodejs",
        "nodejs10.x": "nodejs",
        "nodejs12.x": "nodejs",
        "ruby2.5": "ruby/lib",
        "ruby2.7": "ruby/lib",
        "java8": "java",
        "java11": "java",
        "java8.al2": "java",
        # User is responsible for creating subfolder in these workflows
        "makefile": "",
    }

    if build_workflow not in subfolders_by_runtime:
        raise UnsupportedRuntimeException("'{}' runtime is not supported for layers".format(build_workflow))

    return subfolders_by_runtime[build_workflow]


def get_workflow_config(runtime, code_dir, project_dir, specified_workflow=None):
    """
    Get a workflow config that corresponds to the runtime provided. This method examines contents of the project
    and code directories to determine the most appropriate workflow for the given runtime. Currently the decision is
    based on the presence of a supported manifest file. For runtimes that have more than one workflow, we choose a
    workflow by examining ``code_dir`` followed by ``project_dir`` for presence of a supported manifest.

    Parameters
    ----------
    runtime str
        The runtime of the config

    code_dir str
        Directory where Lambda function code is present

    project_dir str
        Root of the Serverless application project.

    specified_workflow str
        Workflow to be used, if directly specified. They are currently scoped to "makefile" and the official runtime
        identifier names themselves, eg: nodejs10.x. If a workflow is not directly specified, it is calculated by the current method
        based on the runtime.

    Returns
    -------
    namedtuple(Capability)
        namedtuple that represents the Builder Workflow Config
    """

    selectors_by_build_method = {"makefile": BasicWorkflowSelector(PROVIDED_MAKE_CONFIG)}

    selectors_by_runtime = {
        "python2.7": BasicWorkflowSelector(PYTHON_PIP_CONFIG),
        "python3.6": BasicWorkflowSelector(PYTHON_PIP_CONFIG),
        "python3.7": BasicWorkflowSelector(PYTHON_PIP_CONFIG),
        "python3.8": BasicWorkflowSelector(PYTHON_PIP_CONFIG),
        "nodejs10.x": BasicWorkflowSelector(NODEJS_NPM_CONFIG),
        "nodejs12.x": BasicWorkflowSelector(NODEJS_NPM_CONFIG),
        "ruby2.5": BasicWorkflowSelector(RUBY_BUNDLER_CONFIG),
        "ruby2.7": BasicWorkflowSelector(RUBY_BUNDLER_CONFIG),
        "dotnetcore2.1": BasicWorkflowSelector(DOTNET_CLIPACKAGE_CONFIG),
        "dotnetcore3.1": BasicWorkflowSelector(DOTNET_CLIPACKAGE_CONFIG),
        "go1.x": BasicWorkflowSelector(GO_MOD_CONFIG),
        # When Maven builder exists, add to this list so we can automatically choose a builder based on the supported
        # manifest
        "java8": ManifestWorkflowSelector(
            [
                # Gradle builder needs custom executable paths to find `gradlew` binary
                JAVA_GRADLE_CONFIG._replace(executable_search_paths=[code_dir, project_dir]),
                JAVA_KOTLIN_GRADLE_CONFIG._replace(executable_search_paths=[code_dir, project_dir]),
                JAVA_MAVEN_CONFIG,
            ]
        ),
        "java11": ManifestWorkflowSelector(
            [
                # Gradle builder needs custom executable paths to find `gradlew` binary
                JAVA_GRADLE_CONFIG._replace(executable_search_paths=[code_dir, project_dir]),
                JAVA_KOTLIN_GRADLE_CONFIG._replace(executable_search_paths=[code_dir, project_dir]),
                JAVA_MAVEN_CONFIG,
            ]
        ),
        "java8.al2": ManifestWorkflowSelector(
            [
                # Gradle builder needs custom executable paths to find `gradlew` binary
                JAVA_GRADLE_CONFIG._replace(executable_search_paths=[code_dir, project_dir]),
                JAVA_KOTLIN_GRADLE_CONFIG._replace(executable_search_paths=[code_dir, project_dir]),
                JAVA_MAVEN_CONFIG,
            ]
        ),
        "provided": BasicWorkflowSelector(PROVIDED_MAKE_CONFIG),
        "provided.al2": BasicWorkflowSelector(PROVIDED_MAKE_CONFIG),
    }
    # First check if the runtime is present and is buildable, if not raise an UnsupportedRuntimeException Error.
    # If runtime is present it should be in selectors_by_runtime, however for layers there will be no runtime so in that case
    # we move ahead and resolve to any matching workflow from both types.
    if runtime and runtime not in selectors_by_runtime:
        raise UnsupportedRuntimeException("'{}' runtime is not supported".format(runtime))

    try:
        # Identify appropriate workflow selector.
        selector = get_selector(
            selector_list=[selectors_by_build_method, selectors_by_runtime],
            identifiers=[specified_workflow, runtime],
            specified_workflow=specified_workflow,
        )

        # Identify workflow configuration from the workflow selector.
        config = selector.get_config(code_dir, project_dir)
        return config
    except ValueError as ex:
        raise UnsupportedRuntimeException(
            "Unable to find a supported build workflow for runtime '{}'. Reason: {}".format(runtime, str(ex))
        ) from ex


def supports_build_in_container(config):
    """
    Given a workflow config, this method provides a boolean on whether the workflow can run within a container or not.

    Parameters
    ----------
    config namedtuple(Capability)
        Config specifying the particular build workflow

    Returns
    -------
    tuple(bool, str)
        True, if this workflow can be built inside a container. False, along with a reason message if it cannot be.
    """

    def _key(c):
        return str(c.language) + str(c.dependency_manager) + str(c.application_framework)

    # This information could have beeen bundled inside the Workflow Config object. But we this way because
    # ultimately the workflow's implementation dictates whether it can run within a container or not.
    # A "workflow config" is like a primary key to identify the workflow. So we use the config as a key in the
    # map to identify which workflows can support building within a container.

    unsupported = {
        _key(DOTNET_CLIPACKAGE_CONFIG): "We do not support building .NET Core Lambda functions within a container. "
        "Try building without the container. Most .NET Core functions will build "
        "successfully.",
        _key(GO_MOD_CONFIG): "We do not support building Go Lambda functions within a container. "
        "Try building without the container. Most Go functions will build "
        "successfully.",
    }

    thiskey = _key(config)
    if thiskey in unsupported:
        return False, unsupported[thiskey]

    return True, None


class BasicWorkflowSelector:
    """
    Basic workflow selector that returns the first available configuration in the given list of configurations
    """

    def __init__(self, configs):
        if not isinstance(configs, list):
            configs = [configs]

        self.configs = configs

    def get_config(self, code_dir, project_dir):
        """
        Returns the first available configuration
        """
        return self.configs[0]


class ManifestWorkflowSelector(BasicWorkflowSelector):
    """
    Selects a workflow by examining the directories for presence of a supported manifest
    """

    def get_config(self, code_dir, project_dir):
        """
        Finds a configuration by looking for a manifest in the given directories.

        Returns
        -------
        samcli.lib.build.workflow_config.CONFIG
            A supported configuration if one is found

        Raises
        ------
        ValueError
            If none of the supported manifests files are found
        """

        # Search for manifest first in code directory and then in the project directory.
        # Search order is important here because we want to prefer the manifest present within the code directory over
        # a manifest present in project directory.
        search_dirs = [code_dir, project_dir]
        LOG.debug("Looking for a supported build workflow in following directories: %s", search_dirs)

        for config in self.configs:

            if any([self._has_manifest(config, directory) for directory in search_dirs]):
                return config

        raise ValueError(
            "None of the supported manifests '{}' were found in the following paths '{}'".format(
                [config.manifest_name for config in self.configs], search_dirs
            )
        )

    @staticmethod
    def _has_manifest(config, directory):
        return os.path.exists(os.path.join(directory, config.manifest_name))
