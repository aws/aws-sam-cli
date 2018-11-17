"""
Builds the application
"""

import sys
import os
import io
import json
import logging
import tempfile

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

from collections import namedtuple

import samcli.lib.utils.osutils as osutils
from samcli.local.docker.lambda_build_container import LambdaBuildContainer
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import LambdaBuilderError
from aws_lambda_builders import RPC_PROTOCOL_VERSION as lambda_builders_protocol_version


LOG = logging.getLogger(__name__)


class UnsupportedRuntimeException(Exception):
    pass


class UnsupportedBuilderLibraryVersionError(Exception):
    pass


class BuildError(Exception):
    pass


def _get_workflow_config(runtime):

    Config = namedtuple('Capability', ["language", "dependency_manager", "application_framework", "manifest_name"])

    if runtime.startswith("python"):
        return Config(
            language="python",
            dependency_manager="pip",
            application_framework=None,
            manifest_name="requirements.txt")
    else:
        raise UnsupportedRuntimeException("'%s' runtime is not supported".format(runtime))


class ApplicationBuilder(object):
    """
    Class to build an entire application. Currently, this class builds Lambda functions only, but there is nothing that
    is stopping this class from supporting other resource types. Building in context of Lambda functions refer to
    converting source code into artifacts that can be run on AWS Lambda
    """

    def __init__(self,
                 function_provider,
                 build_dir,
                 base_dir,
                 manifest_path_override=None,
                 container_manager=None,
                 parallel=False):
        """
        Initialize the class

        Parameters
        ----------
        function_provider : samcli.commands.local.lib.sam_function_provider.SamFunctionProvider
            Provider that can vend out functions available in the SAM template

        build_dir : str
            Path to the directory where we will be storing built artifacts

        base_dir : str
            Path to a folder. Use this folder as the root to resolve relative source code paths against

        container_manager : samcli.local.docker.manager.ContainerManager
            Optional. If provided, we will attempt to build inside a Docker Container

        parallel : bool
            Optional. Set to True to build each function in parallel to improve performance
        """
        self.function_provider = function_provider
        self.build_dir = build_dir
        self.base_dir = base_dir
        self.manifest_path_override = manifest_path_override

        self.container_manager = container_manager
        self.parallel = parallel

    def build(self):
        """
        Build the entire application

        Returns
        -------
        dict
            Returns the path to where each resource was built as a map of resource's LogicalId to the path string
        """

        result = {}

        for lambda_function in self.function_provider.get_all():

            LOG.info("Building resource '%s'", lambda_function.name)
            result[lambda_function.name] = self._build_function(lambda_function.name,
                                                                lambda_function.codeuri,
                                                                lambda_function.runtime)

        return result

    def update_template(self, template_dict, target_template_path, built_artifacts):
        """
        Given the path to built artifacts, update the template to point appropriate resource CodeUris to the artifacts
        folder

        Parameters
        ----------
        template_dict
        built_artifacts : dict
            Map of LogicalId of a resource to the path where the the built artifacts for this resource lives

        Returns
        -------
        dict
            Updated template
        """
        # TODO: Move this method to a "build provider" or some other class. It doesn't really fit within here.

        target_dir = os.path.dirname(target_template_path)

        for logical_id, resource in template_dict.get("Resources", {}).items():

            if logical_id not in built_artifacts:
                # this resource was not built. So skip it
                continue

            # Artifacts are written relative to the output template because it makes the template portability
            #   Ex: A CI/CD pipeline build stage could zip the output folder and pass to a
            #   package stage running on a different machine
            artifact_relative_path = os.path.relpath(built_artifacts[logical_id], target_dir)

            resource_type = resource.get("Type")
            if resource_type == "AWS::Serverless::Function":
                template_dict["Resources"][logical_id]["Properties"]["CodeUri"] = artifact_relative_path

            if resource_type == "AWS::Lambda::Function":
                template_dict["Resources"][logical_id]["Properties"]["Code"] = artifact_relative_path

        return template_dict

    def _build_function(self, function_name, codeuri, runtime):

        config = _get_workflow_config(runtime)

        # Create the arguments to pass to the builder

        # Code is always relative to the given base directory.
        code_dir = str(pathlib.Path(self.base_dir, codeuri).resolve())

        # artifacts directory will be created by the builder
        artifacts_dir = str(pathlib.Path(self.build_dir, function_name))

        with osutils.mkdir_temp() as scratch_dir:
            manifest_path = self.manifest_path_override or os.path.join(code_dir, config.manifest_name)

            # By default prefer to build in-process for speed
            build_method = self._build_function_in_process
            if self.container_manager:
                build_method = self._build_function_on_container

            return build_method(config,
                                code_dir,
                                artifacts_dir,
                                scratch_dir,
                                manifest_path,
                                runtime)

    def _build_function_in_process(self,
                                   config,
                                   source_dir,
                                   artifacts_dir,
                                   scratch_dir,
                                   manifest_path,
                                   runtime):

        builder = LambdaBuilder(language=config.language,
                                dependency_manager=config.dependency_manager,
                                application_framework=config.application_framework)

        try:
            builder.build(source_dir,
                          artifacts_dir,
                          scratch_dir,
                          manifest_path,
                          runtime=runtime)
        except LambdaBuilderError as ex:
            raise BuildError(str(ex))

        return artifacts_dir

    def _build_function_on_container(self,
                                     config,
                                     source_dir,
                                     artifacts_dir,
                                     scratch_dir,
                                     manifest_path,
                                     runtime):

        # If we are printing debug logs in SAM CLI, the builder library should also print debug logs
        log_level = LOG.getEffectiveLevel()

        container = LambdaBuildContainer(lambda_builders_protocol_version,
                                         config.language,
                                         config.dependency_manager,
                                         config.application_framework,
                                         source_dir,
                                         manifest_path,
                                         runtime,
                                         log_level=log_level,
                                         optimizations=None,
                                         options=None)

        self.container_manager.run(container)

        # Container's output provides status of whether the build succeeded or failed
        # stdout contains the result of JSON-RPC call
        stdout_stream = io.BytesIO()
        # stderr contains logs printed by the builder
        stderr_stream = sys.stderr.buffer if sys.version_info.major > 2 else sys.stderr  # pylint: disable=no-member
        container.wait_for_logs(stdout=stdout_stream, stderr=stderr_stream)

        stdout_data = stdout_stream.getvalue().decode('utf-8')
        LOG.debug("Build inside container returned response %s", stdout_data)

        try:
            response = json.loads(stdout_data)
        except Exception:
            # Invalid JSON is produced as an output only when the builder process crashed for some reason.
            # Report this as a crash
            LOG.debug("Builder crashed")
            raise

        if "error" in response:
            error = response.get("error", {})
            err_code = error.get("code")
            msg = error.get("message")

            if 400 <= err_code < 500:
                # Like HTTP 4xx - customer error
                raise BuildError(msg)

            if err_code == 505:
                # Like HTTP 505 error code: Version of the protocol is not supported
                # In this case, this error means that the Builder Library within the container is
                # not compatible with the version of protocol expected SAM CLI installation supports.
                # This can happen when customers have a newer container image or an older SAM CLI version.
                # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/505
                raise UnsupportedBuilderLibraryVersionError(msg)

            if err_code == -32601:
                # Default JSON Rpc Code for Method Unavailable https://www.jsonrpc.org/specification
                # This can happen if customers are using an incompatible version of builder library within the
                # container
                LOG.debug("Builder library does not support the supplied method")
                raise UnsupportedBuilderLibraryVersionError(msg)

            else:
                LOG.debug("Builder crashed")
                raise ValueError(msg)

        # Request is successful. Now copy the artifacts back to the host
        LOG.debug("Build inside container was successful. Copying artifacts from container to host")

        # "/." is a Docker thing that instructions the copy command to download contents of the folder only
        result_dir_in_container = response["result"]["artifacts_dir"] + "/."
        container.copy(result_dir_in_container, artifacts_dir)

        LOG.debug("Build inside container succeeded")
        return artifacts_dir
