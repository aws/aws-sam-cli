"""
Builds the application
"""

import os
import io
import json
import logging

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

import docker

import samcli.lib.utils.osutils as osutils
from samcli.local.docker.lambda_build_container import LambdaBuildContainer
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import LambdaBuilderError
from aws_lambda_builders import RPC_PROTOCOL_VERSION as lambda_builders_protocol_version
from .workflow_config import get_workflow_config


LOG = logging.getLogger(__name__)


class UnsupportedBuilderLibraryVersionError(Exception):

    def __init__(self, container_name, error_msg):
        msg = "You are running an outdated version of Docker container '{container_name}' that is not compatible with" \
              "this version of SAM CLI. Please upgrade to continue to continue with build. Reason: '{error_msg}'"
        Exception.__init__(self, msg.format(container_name=container_name, error_msg=error_msg))


class BuildError(Exception):
    pass


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
        self._function_provider = function_provider
        self._build_dir = build_dir
        self._base_dir = base_dir
        self._manifest_path_override = manifest_path_override

        self._container_manager = container_manager
        self._parallel = parallel

    def build(self):
        """
        Build the entire application

        Returns
        -------
        dict
            Returns the path to where each resource was built as a map of resource's LogicalId to the path string
        """

        result = {}

        for lambda_function in self._function_provider.get_all():

            LOG.info("Building resource '%s'", lambda_function.name)
            result[lambda_function.name] = self._build_function(lambda_function.name,
                                                                lambda_function.codeuri,
                                                                lambda_function.runtime)

        return result

    def update_template(self, template_dict, original_template_path, built_artifacts):
        """
        Given the path to built artifacts, update the template to point appropriate resource CodeUris to the artifacts
        folder

        Parameters
        ----------
        template_dict
        original_template_path : str
            Path where the template file will be written to

        built_artifacts : dict
            Map of LogicalId of a resource to the path where the the built artifacts for this resource lives

        Returns
        -------
        dict
            Updated template
        """

        original_dir = os.path.dirname(original_template_path)

        for logical_id, resource in template_dict.get("Resources", {}).items():

            if logical_id not in built_artifacts:
                # this resource was not built. So skip it
                continue

            # Artifacts are written relative to the template because it makes the template portable
            #   Ex: A CI/CD pipeline build stage could zip the output folder and pass to a
            #   package stage running on a different machine
            artifact_relative_path = os.path.relpath(built_artifacts[logical_id], original_dir)

            resource_type = resource.get("Type")
            properties = resource.setdefault("Properties", {})
            if resource_type == "AWS::Serverless::Function":
                properties["CodeUri"] = artifact_relative_path

            if resource_type == "AWS::Lambda::Function":
                properties["Code"] = artifact_relative_path

        return template_dict

    def _build_function(self, function_name, codeuri, runtime):
        """
        Given the function information, this method will build the Lambda function. Depending on the configuration
        it will either build the function in process or by spinning up a Docker container.

        Parameters
        ----------
        function_name : str
            Name or LogicalId of the function

        codeuri : str
            Path to where the code lives

        runtime : str
            AWS Lambda function runtime

        Returns
        -------
        str
            Path to the location where built artifacts are available
        """

        # Create the arguments to pass to the builder
        # Code is always relative to the given base directory.
        code_dir = str(pathlib.Path(self._base_dir, codeuri).resolve())

        config = get_workflow_config(runtime, code_dir, self._base_dir)

        # artifacts directory will be created by the builder
        artifacts_dir = str(pathlib.Path(self._build_dir, function_name))

        with osutils.mkdir_temp() as scratch_dir:
            manifest_path = self._manifest_path_override or os.path.join(code_dir, config.manifest_name)

            # By default prefer to build in-process for speed
            build_method = self._build_function_in_process
            if self._container_manager:
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
                          runtime=runtime,
                          executable_search_paths=config.executable_search_paths)
        except LambdaBuilderError as ex:
            raise BuildError(str(ex))

        return artifacts_dir

    def _build_function_on_container(self,  # pylint: disable=too-many-locals
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
                                         options=None,
                                         executable_search_paths=config.executable_search_paths)

        try:
            try:
                self._container_manager.run(container)
            except docker.errors.APIError as ex:
                if "executable file not found in $PATH" in str(ex):
                    raise UnsupportedBuilderLibraryVersionError(container.image,
                                                                "{} executable not found in container"
                                                                .format(container.executable_name))

            # Container's output provides status of whether the build succeeded or failed
            # stdout contains the result of JSON-RPC call
            stdout_stream = io.BytesIO()
            # stderr contains logs printed by the builder. Stream it directly to terminal
            stderr_stream = osutils.stderr()
            container.wait_for_logs(stdout=stdout_stream, stderr=stderr_stream)

            stdout_data = stdout_stream.getvalue().decode('utf-8')
            LOG.debug("Build inside container returned response %s", stdout_data)

            response = self._parse_builder_response(stdout_data, container.image)

            # Request is successful. Now copy the artifacts back to the host
            LOG.debug("Build inside container was successful. Copying artifacts from container to host")

            # "/." is a Docker thing that instructions the copy command to download contents of the folder only
            result_dir_in_container = response["result"]["artifacts_dir"] + "/."
            container.copy(result_dir_in_container, artifacts_dir)
        finally:
            self._container_manager.stop(container)

        LOG.debug("Build inside container succeeded")
        return artifacts_dir

    @staticmethod
    def _parse_builder_response(stdout_data, image_name):

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
                raise UnsupportedBuilderLibraryVersionError(image_name, msg)

            if err_code == -32601:
                # Default JSON Rpc Code for Method Unavailable https://www.jsonrpc.org/specification
                # This can happen if customers are using an incompatible version of builder library within the
                # container
                LOG.debug("Builder library does not support the supplied method")
                raise UnsupportedBuilderLibraryVersionError(image_name, msg)

            else:
                LOG.debug("Builder crashed")
                raise ValueError(msg)

        return response
