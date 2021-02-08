"""
Builds the application
"""

import os
import io
import json
import logging
import pathlib
from typing import List, Optional, Dict, cast

import docker
import docker.errors
from aws_lambda_builders import RPC_PROTOCOL_VERSION as lambda_builders_protocol_version
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import LambdaBuilderError

from samcli.lib.build.build_graph import FunctionBuildDefinition, LayerBuildDefinition, BuildGraph
from samcli.lib.build.build_strategy import (
    DefaultBuildStrategy,
    CachedBuildStrategy,
    ParallelBuildStrategy,
    BuildStrategy,
)
from samcli.lib.providers.provider import ResourcesToBuildCollector
from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.utils.colors import Colored
import samcli.lib.utils.osutils as osutils
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.docker.lambda_build_container import LambdaBuildContainer
from samcli.local.docker.utils import is_docker_reachable
from samcli.local.docker.manager import ContainerManager
from .exceptions import (
    DockerConnectionError,
    DockerfileOutSideOfContext,
    DockerBuildFailed,
    BuildError,
    BuildInsideContainerError,
    ContainerBuildNotSupported,
    UnsupportedBuilderLibraryVersionError,
)
from .workflow_config import get_workflow_config, get_layer_subfolder, supports_build_in_container, CONFIG

LOG = logging.getLogger(__name__)


class ApplicationBuilder:
    """
    Class to build an entire application. Currently, this class builds Lambda functions only, but there is nothing that
    is stopping this class from supporting other resource types. Building in context of Lambda functions refer to
    converting source code into artifacts that can be run on AWS Lambda
    """

    def __init__(
        self,
        resources_to_build: ResourcesToBuildCollector,
        build_dir: str,
        base_dir: str,
        cache_dir: str,
        cached: bool = False,
        is_building_specific_resource: bool = False,
        manifest_path_override: Optional[str] = None,
        container_manager: Optional[ContainerManager] = None,
        parallel: bool = False,
        mode: Optional[str] = None,
        stream_writer: Optional[StreamWriter] = None,
        docker_client: Optional[docker.DockerClient] = None,
    ) -> None:
        """
        Initialize the class

        Parameters
        ----------
        resources_to_build: Iterator
            Iterator that can vend out resources available in the SAM template

        build_dir : str
            Path to the directory where we will be storing built artifacts

        base_dir : str
            Path to a folder. Use this folder as the root to resolve relative source code paths against

        cache_dir : str
            Path to a the directory where we will be caching built artifacts

        cached:
            Optional. Set to True to build each function with cache to improve performance

        is_building_specific_resource : boolean
            Whether customer requested to build a specific resource alone in isolation,
            by specifying function_identifier to the build command.
            Ex: sam build MyServerlessFunction

        container_manager : samcli.local.docker.manager.ContainerManager
            Optional. If provided, we will attempt to build inside a Docker Container

        parallel : bool
            Optional. Set to True to build each function in parallel to improve performance

        mode : str
            Optional, name of the build mode to use ex: 'debug'
        """
        self._resources_to_build = resources_to_build
        self._build_dir = build_dir
        self._base_dir = base_dir
        self._cache_dir = cache_dir
        self._cached = cached
        self._manifest_path_override = manifest_path_override
        self._is_building_specific_resource = is_building_specific_resource

        self._container_manager = container_manager
        self._parallel = parallel
        self._mode = mode
        self._stream_writer = stream_writer if stream_writer else StreamWriter(osutils.stderr())
        self._docker_client = docker_client if docker_client else docker.from_env()

        self._deprecated_runtimes = {"nodejs4.3", "nodejs6.10", "nodejs8.10", "dotnetcore2.0"}
        self._colored = Colored()

    def build(self) -> Dict[str, str]:
        """
        Build the entire application

        Returns
        -------
        dict
            Returns the path to where each resource was built as a map of resource's LogicalId to the path string
        """
        build_graph = self._get_build_graph()
        build_strategy: BuildStrategy = DefaultBuildStrategy(
            build_graph, self._build_dir, self._build_function, self._build_layer
        )

        if self._parallel:
            if self._cached:
                build_strategy = ParallelBuildStrategy(
                    build_graph,
                    CachedBuildStrategy(
                        build_graph,
                        build_strategy,
                        self._base_dir,
                        self._build_dir,
                        self._cache_dir,
                        self._is_building_specific_resource,
                    ),
                )
            else:
                build_strategy = ParallelBuildStrategy(build_graph, build_strategy)
        elif self._cached:
            build_strategy = CachedBuildStrategy(
                build_graph,
                build_strategy,
                self._base_dir,
                self._build_dir,
                self._cache_dir,
                self._is_building_specific_resource,
            )

        return build_strategy.build()

    def _get_build_graph(self) -> BuildGraph:
        """
        Converts list of functions and layers into a build graph, where we can iterate on each unique build and trigger
        build
        :return: BuildGraph, which represents list of unique build definitions
        """
        build_graph = BuildGraph(self._build_dir)
        functions = self._resources_to_build.functions
        layers = self._resources_to_build.layers
        for function in functions:
            function_build_details = FunctionBuildDefinition(
                function.runtime, function.codeuri, function.packagetype, function.metadata
            )
            build_graph.put_function_build_definition(function_build_details, function)

        for layer in layers:
            layer_build_details = LayerBuildDefinition(
                layer.name, layer.codeuri, layer.build_method, layer.compatible_runtimes
            )
            build_graph.put_layer_build_definition(layer_build_details, layer)

        build_graph.clean_redundant_definitions_and_update(not self._is_building_specific_resource)
        return build_graph

    @staticmethod
    def update_template(template_dict: Dict, original_template_path: str, built_artifacts: Dict[str, str]) -> Dict:
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

        original_dir = pathlib.Path(original_template_path).parent.resolve()

        for logical_id, resource in template_dict.get("Resources", {}).items():

            if logical_id not in built_artifacts:
                # this resource was not built. So skip it
                continue

            artifact_dir = pathlib.Path(built_artifacts[logical_id]).resolve()

            # Default path to absolute path of the artifact
            store_path = str(artifact_dir)

            # In Windows, if template and artifacts are in two different drives, relpath will fail
            if original_dir.drive == artifact_dir.drive:
                # Artifacts are written relative  the template because it makes the template portable
                #   Ex: A CI/CD pipeline build stage could zip the output folder and pass to a
                #   package stage running on a different machine
                store_path = os.path.relpath(artifact_dir, original_dir)

            resource_type = resource.get("Type")
            properties = resource.setdefault("Properties", {})

            if resource_type == SamBaseProvider.SERVERLESS_FUNCTION and properties.get("PackageType", ZIP) == ZIP:
                properties["CodeUri"] = store_path

            if resource_type == SamBaseProvider.LAMBDA_FUNCTION and properties.get("PackageType", ZIP) == ZIP:
                properties["Code"] = store_path

            if resource_type in [SamBaseProvider.SERVERLESS_LAYER, SamBaseProvider.LAMBDA_LAYER]:
                properties["ContentUri"] = store_path

            if resource_type == SamBaseProvider.LAMBDA_FUNCTION and properties.get("PackageType", ZIP) == IMAGE:
                properties["Code"] = built_artifacts[logical_id]

            if resource_type == SamBaseProvider.SERVERLESS_FUNCTION and properties.get("PackageType", ZIP) == IMAGE:
                properties["ImageUri"] = built_artifacts[logical_id]

        return template_dict

    def _build_lambda_image(self, function_name: str, metadata: Dict) -> str:
        """
        Build an Lambda image

        Parameters
        ----------
        function_name str
            Name of the function (logical id or function name)
        metadata dict
            Dictionary representing the Metadata attached to the Resource in the template

        Returns
        -------
        str
            The full tag (org/repo:tag) of the image that was built
        """

        LOG.info("Building image for %s function", function_name)

        dockerfile = cast(str, metadata.get("Dockerfile"))
        docker_context = cast(str, metadata.get("DockerContext"))
        # Have a default tag if not present.
        tag = metadata.get("DockerTag", "latest")
        docker_tag = f"{function_name.lower()}:{tag}"
        docker_build_args = metadata.get("DockerBuildArgs", {})
        if not isinstance(docker_build_args, dict):
            raise DockerBuildFailed("DockerBuildArgs needs to be a dictionary!")

        docker_context_dir = pathlib.Path(self._base_dir, docker_context).resolve()
        if not is_docker_reachable(self._docker_client):
            raise DockerConnectionError(msg=f"Building image for {function_name} requires Docker. is Docker running?")

        if os.environ.get("SAM_BUILD_MODE") and isinstance(docker_build_args, dict):
            docker_build_args["SAM_BUILD_MODE"] = os.environ.get("SAM_BUILD_MODE")
            docker_tag = "-".join([docker_tag, docker_build_args["SAM_BUILD_MODE"]])

        if isinstance(docker_build_args, dict):
            LOG.info("Setting DockerBuildArgs: %s for %s function", docker_build_args, function_name)

        build_logs = self._docker_client.api.build(
            path=str(docker_context_dir),
            dockerfile=dockerfile,
            tag=docker_tag,
            buildargs=docker_build_args,
            decode=True,
        )

        # The Docker-py low level api will stream logs back but if an exception is raised by the api
        # this is raised when accessing the generator. So we need to wrap accessing build_logs in a try: except.
        try:
            self._stream_lambda_image_build_logs(build_logs, function_name)
        except docker.errors.APIError as e:
            if e.is_server_error and "Cannot locate specified Dockerfile" in e.explanation:
                raise DockerfileOutSideOfContext(e.explanation) from e

            # Not sure what else can be raise that we should be catching but re-raising for now
            raise

        return docker_tag

    def _stream_lambda_image_build_logs(self, build_logs: List[Dict[str, str]], function_name: str) -> None:
        """
        Stream logs to the console from an Lambda image build.

        Parameters
        ----------
        build_logs generator
            A generator for the build output.
        function_name str
            Name of the function that is being built

        Returns
        -------
        None
        """
        for log in build_logs:
            if log:
                log_stream = log.get("stream")
                error_stream = log.get("error")

                if error_stream:
                    raise DockerBuildFailed(f"{function_name} failed to build: {error_stream}")

                if log_stream:
                    self._stream_writer.write(str.encode(log_stream))
                    self._stream_writer.flush()

    def _build_layer(
        self, layer_name: str, codeuri: str, specified_workflow: str, compatible_runtimes: List[str]
    ) -> str:
        # Create the arguments to pass to the builder
        # Code is always relative to the given base directory.
        code_dir = str(pathlib.Path(self._base_dir, codeuri).resolve())

        config = get_workflow_config(None, code_dir, self._base_dir, specified_workflow)
        subfolder = get_layer_subfolder(specified_workflow)

        # artifacts directory will be created by the builder
        artifacts_dir = str(pathlib.Path(self._build_dir, layer_name, subfolder))

        with osutils.mkdir_temp() as scratch_dir:
            manifest_path = self._manifest_path_override or os.path.join(code_dir, config.manifest_name)

            # By default prefer to build in-process for speed
            build_runtime = specified_workflow
            build_method = self._build_function_in_process
            if self._container_manager:
                build_method = self._build_function_on_container
                if config.language == "provided":
                    LOG.warning(
                        "For container layer build, first compatible runtime is chosen as build target for container."
                    )
                    # Only set to this value if specified workflow is makefile
                    # which will result in config language as provided
                    build_runtime = compatible_runtimes[0]
            options = ApplicationBuilder._get_build_options(layer_name, config.language, None)

            build_method(config, code_dir, artifacts_dir, scratch_dir, manifest_path, build_runtime, options)
            # Not including subfolder in return so that we copy subfolder, instead of copying artifacts inside it.
            return str(pathlib.Path(self._build_dir, layer_name))

    def _build_function(  # pylint: disable=R1710
        self,
        function_name: str,
        codeuri: str,
        packagetype: str,
        runtime: str,
        handler: Optional[str],
        artifacts_dir: str,
        metadata: Optional[Dict] = None,
    ) -> str:
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

        artifacts_dir: str
            Path to where function will be build into

        metadata : dict
            AWS Lambda function metadata

        Returns
        -------
        str
            Path to the location where built artifacts are available
        """
        if packagetype == IMAGE:
            # pylint: disable=fixme
            # FIXME: _build_lambda_image assumes metadata is not None, we need to throw an exception here
            return self._build_lambda_image(function_name=function_name, metadata=metadata)  # type: ignore
        if packagetype == ZIP:
            if runtime in self._deprecated_runtimes:
                message = (
                    f"WARNING: {runtime} is no longer supported by AWS Lambda, "
                    "please update to a newer supported runtime. SAM CLI "
                    f"will drop support for all deprecated runtimes {self._deprecated_runtimes} on May 1st. "
                    "See issue: https://github.com/awslabs/aws-sam-cli/issues/1934 for more details."
                )
                LOG.warning(self._colored.yellow(message))

            # Create the arguments to pass to the builder
            # Code is always relative to the given base directory.
            code_dir = str(pathlib.Path(self._base_dir, codeuri).resolve())

            # Determine if there was a build workflow that was specified directly in the template.
            specified_build_workflow = metadata.get("BuildMethod", None) if metadata else None

            config = get_workflow_config(runtime, code_dir, self._base_dir, specified_workflow=specified_build_workflow)

            with osutils.mkdir_temp() as scratch_dir:
                manifest_path = self._manifest_path_override or os.path.join(code_dir, config.manifest_name)

                # By default prefer to build in-process for speed
                build_method = self._build_function_in_process
                if self._container_manager:
                    build_method = self._build_function_on_container

                options = ApplicationBuilder._get_build_options(function_name, config.language, handler)

                return build_method(config, code_dir, artifacts_dir, scratch_dir, manifest_path, runtime, options)

        # pylint: disable=fixme
        # FIXME: we need to throw an exception here, packagetype could be something else
        return  # type: ignore

    @staticmethod
    def _get_build_options(function_name: str, language: str, handler: Optional[str]) -> Optional[Dict]:
        """
        Parameters
        ----------
        function_name str
            currrent function resource name
        language str
            language of the runtime
        handler str
            Handler value of the Lambda Function Resource
        Returns
        -------
        dict
            Dictionary that represents the options to pass to the builder workflow or None if options are not needed
        """

        _build_options: Dict = {
            "go": {"artifact_executable_name": handler},
            "provided": {"build_logical_id": function_name},
        }
        return _build_options.get(language, None)

    def _build_function_in_process(
        self,
        config: CONFIG,
        source_dir: str,
        artifacts_dir: str,
        scratch_dir: str,
        manifest_path: str,
        runtime: str,
        options: Optional[dict],
    ) -> str:

        builder = LambdaBuilder(
            language=config.language,
            dependency_manager=config.dependency_manager,
            application_framework=config.application_framework,
        )

        runtime = runtime.replace(".al2", "")

        try:
            builder.build(
                source_dir,
                artifacts_dir,
                scratch_dir,
                manifest_path,
                runtime=runtime,
                executable_search_paths=config.executable_search_paths,
                mode=self._mode,
                options=options,
            )
        except LambdaBuilderError as ex:
            raise BuildError(wrapped_from=ex.__class__.__name__, msg=str(ex)) from ex

        return artifacts_dir

    def _build_function_on_container(
        self,  # pylint: disable=too-many-locals
        config: CONFIG,
        source_dir: str,
        artifacts_dir: str,
        scratch_dir: str,
        manifest_path: str,
        runtime: str,
        options: Optional[Dict],
    ) -> str:
        # _build_function_on_container() is only called when self._container_manager if not None
        if not self._container_manager:
            raise RuntimeError("_build_function_on_container() is called when self._container_manager is None.")

        if not self._container_manager.is_docker_reachable:
            raise BuildInsideContainerError(
                "Docker is unreachable. Docker needs to be running to build inside a container."
            )

        container_build_supported, reason = supports_build_in_container(config)
        if not container_build_supported:
            raise ContainerBuildNotSupported(reason)

        # If we are printing debug logs in SAM CLI, the builder library should also print debug logs
        log_level = LOG.getEffectiveLevel()

        container = LambdaBuildContainer(
            lambda_builders_protocol_version,
            config.language,
            config.dependency_manager,
            config.application_framework,
            source_dir,
            manifest_path,
            runtime,
            log_level=log_level,
            optimizations=None,
            options=options,
            executable_search_paths=config.executable_search_paths,
            mode=self._mode,
        )

        try:
            try:
                self._container_manager.run(container)
            except docker.errors.APIError as ex:
                if "executable file not found in $PATH" in str(ex):
                    raise UnsupportedBuilderLibraryVersionError(
                        container.image, "{} executable not found in container".format(container.executable_name)
                    ) from ex

            # Container's output provides status of whether the build succeeded or failed
            # stdout contains the result of JSON-RPC call
            stdout_stream = io.BytesIO()
            # stderr contains logs printed by the builder. Stream it directly to terminal
            stderr_stream = osutils.stderr()
            container.wait_for_logs(stdout=stdout_stream, stderr=stderr_stream)

            stdout_data = stdout_stream.getvalue().decode("utf-8")
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
    def _parse_builder_response(stdout_data: str, image_name: str) -> Dict:

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
                raise BuildInsideContainerError(msg)

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

            LOG.debug("Builder crashed")
            raise ValueError(msg)

        return cast(Dict, response)
