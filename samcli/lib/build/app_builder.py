"""
Builds the application
"""
import os
import io
import json
import logging
import pathlib
from typing import List, Optional, Dict, cast, Union, NamedTuple, Set

import docker
import docker.errors
from aws_lambda_builders import (
    RPC_PROTOCOL_VERSION as lambda_builders_protocol_version,
    __version__ as lambda_builders_version,
)
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import LambdaBuilderError

from samcli.commands.local.lib.exceptions import OverridesNotWellDefinedError
from samcli.lib.build.build_graph import FunctionBuildDefinition, LayerBuildDefinition, BuildGraph
from samcli.lib.build.build_strategy import (
    DefaultBuildStrategy,
    CachedOrIncrementalBuildStrategyWrapper,
    ParallelBuildStrategy,
    BuildStrategy,
)
from samcli.lib.utils.resources import (
    AWS_CLOUDFORMATION_STACK,
    AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_APPLICATION,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
)
from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer
from samcli.lib.docker.log_streamer import LogStreamer, LogStreamError
from samcli.lib.providers.provider import ResourcesToBuildCollector, Function, get_full_path, Stack, LayerVersion
from samcli.lib.utils.colors import Colored
from samcli.lib.utils import osutils
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.docker.lambda_build_container import LambdaBuildContainer
from samcli.local.docker.utils import is_docker_reachable, get_docker_platform
from samcli.local.docker.manager import ContainerManager
from samcli.commands._utils.experimental import get_enabled_experimental_flags
from samcli.lib.build.exceptions import (
    DockerConnectionError,
    DockerfileOutSideOfContext,
    DockerBuildFailed,
    BuildError,
    BuildInsideContainerError,
    ContainerBuildNotSupported,
    UnsupportedBuilderLibraryVersionError,
)

from samcli.lib.build.workflow_config import (
    get_workflow_config,
    get_layer_subfolder,
    supports_build_in_container,
    CONFIG,
    UnsupportedRuntimeException,
)

LOG = logging.getLogger(__name__)

DEPRECATED_RUNTIMES: Set[str] = {
    "nodejs4.3",
    "nodejs6.10",
    "nodejs8.10",
    "nodejs10.x",
    "dotnetcore2.0",
    "dotnetcore2.1",
    "python2.7",
    "ruby2.5",
}
BUILD_PROPERTIES = "BuildProperties"


class ApplicationBuildResult(NamedTuple):
    """
    Result of the application build, build_graph and the built artifacts in dictionary
    """

    build_graph: BuildGraph
    artifacts: Dict[str, str]


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
        container_env_var: Optional[Dict] = None,
        container_env_var_file: Optional[str] = None,
        build_images: Optional[Dict] = None,
        combine_dependencies: bool = True,
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
        manifest_path_override : Optional[str]
            Optional path to manifest file to replace the default one
        container_manager : samcli.local.docker.manager.ContainerManager
            Optional. If provided, we will attempt to build inside a Docker Container
        parallel : bool
            Optional. Set to True to build each function in parallel to improve performance
        mode : str
            Optional, name of the build mode to use ex: 'debug'
        stream_writer : Optional[StreamWriter]
            An optional stream writer to accept stderr output
        docker_client : Optional[docker.DockerClient]
            An optional Docker client object to replace the default one loaded from env
        container_env_var : Optional[Dict]
            An optional dictionary of environment variables to pass to the container
        container_env_var_file : Optional[str]
            An optional path to file that contains environment variables to pass to the container
        build_images : Optional[Dict]
            An optional dictionary of build images to be used for building functions
        combine_dependencies: bool
            An optional bool parameter to inform lambda builders whether we should separate the source code and
            dependencies or not.
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
        self._stream_writer = stream_writer if stream_writer else StreamWriter(stream=osutils.stderr(), auto_flush=True)
        self._docker_client = docker_client if docker_client else docker.from_env()

        self._deprecated_runtimes = DEPRECATED_RUNTIMES
        self._colored = Colored()
        self._container_env_var = container_env_var
        self._container_env_var_file = container_env_var_file
        self._build_images = build_images or {}
        self._combine_dependencies = combine_dependencies

    def build(self) -> ApplicationBuildResult:
        """
        Build the entire application

        Returns
        -------
        ApplicationBuildResult
            Returns the build graph and the path to where each resource was built as a map of resource's LogicalId
            to the path string
        """
        build_graph = self._get_build_graph(self._container_env_var, self._container_env_var_file)
        build_strategy: BuildStrategy = DefaultBuildStrategy(
            build_graph, self._build_dir, self._build_function, self._build_layer
        )

        if self._parallel:
            if self._cached:
                build_strategy = ParallelBuildStrategy(
                    build_graph,
                    CachedOrIncrementalBuildStrategyWrapper(
                        build_graph,
                        build_strategy,
                        self._base_dir,
                        self._build_dir,
                        self._cache_dir,
                        self._manifest_path_override,
                        self._is_building_specific_resource,
                        bool(self._container_manager),
                    ),
                )
            else:
                build_strategy = ParallelBuildStrategy(build_graph, build_strategy)
        elif self._cached:
            build_strategy = CachedOrIncrementalBuildStrategyWrapper(
                build_graph,
                build_strategy,
                self._base_dir,
                self._build_dir,
                self._cache_dir,
                self._manifest_path_override,
                self._is_building_specific_resource,
                bool(self._container_manager),
            )

        return ApplicationBuildResult(build_graph, build_strategy.build())

    def _get_build_graph(
        self, inline_env_vars: Optional[Dict] = None, env_vars_file: Optional[str] = None
    ) -> BuildGraph:
        """
        Converts list of functions and layers into a build graph, where we can iterate on each unique build and trigger
        build
        :return: BuildGraph, which represents list of unique build definitions
        """
        build_graph = BuildGraph(self._build_dir)
        functions = self._resources_to_build.functions
        layers = self._resources_to_build.layers
        file_env_vars = {}
        if env_vars_file:
            try:
                with open(env_vars_file, "r", encoding="utf-8") as fp:
                    file_env_vars = json.load(fp)
            except Exception as ex:
                raise IOError(
                    "Could not read environment variables overrides from file {}: {}".format(env_vars_file, str(ex))
                ) from ex

        for function in functions:
            container_env_vars = self._make_env_vars(function, file_env_vars, inline_env_vars)
            function_build_details = FunctionBuildDefinition(
                function.runtime,
                function.codeuri,
                function.packagetype,
                function.architecture,
                function.metadata,
                function.handler,
                env_vars=container_env_vars,
            )
            build_graph.put_function_build_definition(function_build_details, function)

        for layer in layers:
            container_env_vars = self._make_env_vars(layer, file_env_vars, inline_env_vars)

            layer_build_details = LayerBuildDefinition(
                layer.full_path,
                layer.codeuri,
                layer.build_method,
                layer.compatible_runtimes,
                layer.build_architecture,
                env_vars=container_env_vars,
            )
            build_graph.put_layer_build_definition(layer_build_details, layer)

        build_graph.clean_redundant_definitions_and_update(not self._is_building_specific_resource)
        return build_graph

    @staticmethod
    def update_template(
        stack: Stack,
        built_artifacts: Dict[str, str],
        stack_output_template_path_by_stack_path: Dict[str, str],
    ) -> Dict:
        """
        Given the path to built artifacts, update the template to point appropriate resource CodeUris to the artifacts
        folder

        Parameters
        ----------
        stack: Stack
            The stack object representing the template
        built_artifacts : dict
            Map of LogicalId of a resource to the path where the the built artifacts for this resource lives
        stack_output_template_path_by_stack_path: Dict[str, str]
            A dictionary contains where the template of each stack will be written to

        Returns
        -------
        dict
            Updated template
        """

        original_dir = pathlib.Path(stack.location).parent.resolve()

        template_dict = stack.template_dict
        normalized_resources = stack.resources
        for logical_id, resource in template_dict.get("Resources", {}).items():
            resource_iac_id = ResourceMetadataNormalizer.get_resource_id(resource, logical_id)
            full_path = get_full_path(stack.stack_path, resource_iac_id)
            has_build_artifact = full_path in built_artifacts
            is_stack = full_path in stack_output_template_path_by_stack_path

            if not has_build_artifact and not is_stack:
                # this resource was not built or a nested stack.
                # So skip it because there is no path/uri to update
                continue

            # clone normalized metadata from stack.resources only to built resources
            normalized_metadata = normalized_resources.get(logical_id, {}).get("Metadata")
            if normalized_metadata:
                resource["Metadata"] = normalized_metadata

            resource_type = resource.get("Type")
            properties = resource.setdefault("Properties", {})

            absolute_output_path = pathlib.Path(
                built_artifacts[full_path]
                if has_build_artifact
                else stack_output_template_path_by_stack_path[full_path]
            ).resolve()
            # Default path to absolute path of the artifact
            store_path = str(absolute_output_path)

            # In Windows, if template and artifacts are in two different drives, relpath will fail
            if original_dir.drive == absolute_output_path.drive:
                # Artifacts are written relative  the template because it makes the template portable
                #   Ex: A CI/CD pipeline build stage could zip the output folder and pass to a
                #   package stage running on a different machine
                store_path = os.path.relpath(absolute_output_path, original_dir)

            if has_build_artifact:
                ApplicationBuilder._update_built_resource(
                    built_artifacts[full_path], properties, resource_type, store_path
                )

            if is_stack:
                if resource_type == AWS_SERVERLESS_APPLICATION:
                    properties["Location"] = store_path

                if resource_type == AWS_CLOUDFORMATION_STACK:
                    properties["TemplateURL"] = store_path

        return template_dict

    @staticmethod
    def _update_built_resource(path: str, resource_properties: Dict, resource_type: str, absolute_path: str) -> None:
        if resource_type == AWS_SERVERLESS_FUNCTION and resource_properties.get("PackageType", ZIP) == ZIP:
            resource_properties["CodeUri"] = absolute_path
        if resource_type == AWS_LAMBDA_FUNCTION and resource_properties.get("PackageType", ZIP) == ZIP:
            resource_properties["Code"] = absolute_path
        if resource_type == AWS_LAMBDA_LAYERVERSION:
            resource_properties["Content"] = absolute_path
        if resource_type == AWS_SERVERLESS_LAYERVERSION:
            resource_properties["ContentUri"] = absolute_path
        if resource_type == AWS_LAMBDA_FUNCTION and resource_properties.get("PackageType", ZIP) == IMAGE:
            resource_properties["Code"] = {"ImageUri": path}
        if resource_type == AWS_SERVERLESS_FUNCTION and resource_properties.get("PackageType", ZIP) == IMAGE:
            resource_properties["ImageUri"] = path

    def _build_lambda_image(self, function_name: str, metadata: Dict, architecture: str) -> str:
        """
        Build an Lambda image

        Parameters
        ----------
        function_name str
            Name of the function (logical id or function name)
        metadata dict
            Dictionary representing the Metadata attached to the Resource in the template
        architecture : str
            The architecture type 'x86_64' and 'arm64' in AWS

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
        docker_build_target = metadata.get("DockerBuildTarget", None)
        docker_build_args = metadata.get("DockerBuildArgs", {})

        if not dockerfile or not docker_context:
            raise DockerBuildFailed("Docker file or Docker context metadata are missed.")

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

        build_args = {
            "path": str(docker_context_dir),
            "dockerfile": dockerfile,
            "tag": docker_tag,
            "buildargs": docker_build_args,
            "decode": True,
            "platform": get_docker_platform(architecture),
            "rm": True,
        }
        if docker_build_target:
            build_args["target"] = cast(str, docker_build_target)

        build_logs = self._docker_client.api.build(**build_args)

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
        """
        build_log_streamer = LogStreamer(self._stream_writer)
        try:
            build_log_streamer.stream_progress(build_logs)
        except LogStreamError as ex:
            raise DockerBuildFailed(msg=f"{function_name} failed to build: {str(ex)}") from ex

    def _build_layer(
        self,
        layer_name: str,
        codeuri: str,
        specified_workflow: str,
        compatible_runtimes: List[str],
        architecture: str,
        artifact_dir: str,
        container_env_vars: Optional[Dict] = None,
        dependencies_dir: Optional[str] = None,
        download_dependencies: bool = True,
    ) -> str:
        """
        Given the layer information, this method will build the Lambda layer. Depending on the configuration
        it will either build the function in process or by spinning up a Docker container.

        Parameters
        ----------
        layer_name : str
            Name or LogicalId of the function
        codeuri : str
            Path to where the code lives
        specified_workflow : str
            The specified workflow
        compatible_runtimes : List[str]
            List of runtimes the layer build is compatible with
        architecture : str
            The architecture type 'x86_64' and 'arm64' in AWS
        artifact_dir : str
            Path to where layer will be build into.
            A subfolder will be created in this directory depending on the specified workflow.
        container_env_vars : Optional[Dict]
            An optional dictionary of environment variables to pass to the container.
        dependencies_dir: Optional[str]
            An optional string parameter which will be used in lambda builders for downloading dependencies into
            separate folder
        download_dependencies: bool
            An optional boolean parameter to inform lambda builders whether download dependencies or use previously
            downloaded ones. Default value is True.

        Returns
        -------
        str
            Path to the location where built artifacts are available
        """
        # Create the arguments to pass to the builder
        # Code is always relative to the given base directory.
        code_dir = str(pathlib.Path(self._base_dir, codeuri).resolve())

        config = get_workflow_config(None, code_dir, self._base_dir, specified_workflow)
        subfolder = get_layer_subfolder(specified_workflow)

        # artifacts directory will be created by the builder
        artifact_subdir = str(pathlib.Path(artifact_dir, subfolder))

        with osutils.mkdir_temp() as scratch_dir:
            manifest_path = self._manifest_path_override or os.path.join(code_dir, config.manifest_name)

            # By default prefer to build in-process for speed
            build_runtime = specified_workflow
            options = ApplicationBuilder._get_build_options(layer_name, config.language, None)
            if self._container_manager:
                # None key represents the global build image for all functions/layers
                if config.language == "provided":
                    LOG.warning(
                        "For container layer build, first compatible runtime is chosen as build target for container."
                    )
                    # Only set to this value if specified workflow is makefile
                    # which will result in config language as provided
                    build_runtime = compatible_runtimes[0]
                global_image = self._build_images.get(None)
                image = self._build_images.get(layer_name, global_image)
                self._build_function_on_container(
                    config,
                    code_dir,
                    artifact_subdir,
                    manifest_path,
                    build_runtime,
                    architecture,
                    options,
                    container_env_vars,
                    image,
                    is_building_layer=True,
                )
            else:
                self._build_function_in_process(
                    config,
                    code_dir,
                    artifact_subdir,
                    scratch_dir,
                    manifest_path,
                    build_runtime,
                    architecture,
                    options,
                    dependencies_dir,
                    download_dependencies,
                    True,  # dependencies for layer should always be combined
                    is_building_layer=True,
                )

            # Not including subfolder in return so that we copy subfolder, instead of copying artifacts inside it.
            return artifact_dir

    def _build_function(  # pylint: disable=R1710
        self,
        function_name: str,
        codeuri: str,
        packagetype: str,
        runtime: str,
        architecture: str,
        handler: Optional[str],
        artifact_dir: str,
        metadata: Optional[Dict] = None,
        container_env_vars: Optional[Dict] = None,
        dependencies_dir: Optional[str] = None,
        download_dependencies: bool = True,
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
        packagetype : str
            The package type, 'Zip' or 'Image', see samcli/lib/utils/packagetype.py
        runtime : str
            AWS Lambda function runtime
        architecture : str
            The architecture type 'x86_64' and 'arm64' in AWS
        handler : Optional[str]
            An optional string to specify which function the handler should be
        artifact_dir: str
            Path to where function will be build into
        metadata : dict
            AWS Lambda function metadata
        container_env_vars : Optional[Dict]
            An optional dictionary of environment variables to pass to the container.
        dependencies_dir: Optional[str]
            An optional string parameter which will be used in lambda builders for downloading dependencies into
            separate folder
        download_dependencies: bool
            An optional boolean parameter to inform lambda builders whether download dependencies or use previously
            downloaded ones. Default value is True.

        Returns
        -------
        str
            Path to the location where built artifacts are available
        """
        if packagetype == IMAGE:
            # pylint: disable=fixme
            # FIXME: _build_lambda_image assumes metadata is not None, we need to throw an exception here
            return self._build_lambda_image(
                function_name=function_name, metadata=metadata, architecture=architecture  # type: ignore
            )
        if packagetype == ZIP:
            if runtime in self._deprecated_runtimes:
                message = (
                    f"Building functions with {runtime} is no longer supported by AWS SAM CLI, please "
                    f"update to a newer supported runtime. For more information please check AWS Lambda Runtime "
                    f"Support Policy: https://docs.aws.amazon.com/lambda/latest/dg/runtime-support-policy.html"
                )
                LOG.warning(self._colored.yellow(message))
                raise UnsupportedRuntimeException(f"Building functions with {runtime} is no longer supported")

            # Create the arguments to pass to the builder
            # Code is always relative to the given base directory.
            code_dir = str(pathlib.Path(self._base_dir, codeuri).resolve())

            # Determine if there was a build workflow that was specified directly in the template.
            specified_build_workflow = metadata.get("BuildMethod", None) if metadata else None

            config = get_workflow_config(runtime, code_dir, self._base_dir, specified_workflow=specified_build_workflow)

            with osutils.mkdir_temp() as scratch_dir:
                manifest_path = self._manifest_path_override or os.path.join(code_dir, config.manifest_name)

                options = ApplicationBuilder._get_build_options(
                    function_name, config.language, handler, config.dependency_manager, metadata
                )
                # By default prefer to build in-process for speed
                if self._container_manager:
                    # None represents the global build image for all functions/layers
                    global_image = self._build_images.get(None)
                    image = self._build_images.get(function_name, global_image)

                    return self._build_function_on_container(
                        config,
                        code_dir,
                        artifact_dir,
                        manifest_path,
                        runtime,
                        architecture,
                        options,
                        container_env_vars,
                        image,
                    )

                return self._build_function_in_process(
                    config,
                    code_dir,
                    artifact_dir,
                    scratch_dir,
                    manifest_path,
                    runtime,
                    architecture,
                    options,
                    dependencies_dir,
                    download_dependencies,
                    self._combine_dependencies,
                )

        # pylint: disable=fixme
        # FIXME: we need to throw an exception here, packagetype could be something else
        return  # type: ignore

    @staticmethod
    def _get_build_options(
        function_name: str,
        language: str,
        handler: Optional[str],
        dependency_manager: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Dict]:
        """
        Parameters
        ----------
        function_name str
            currrent function resource name
        language str
            language of the runtime
        handler str
            Handler value of the Lambda Function Resource
        dependency_manager str
            Dependency manager to check in addition to language
        metadata
            Metadata object to search for build properties
        Returns
        -------
        dict
            Dictionary that represents the options to pass to the builder workflow or None if options are not needed
        """
        build_props = {}
        if metadata and isinstance(metadata, dict):
            build_props = metadata.get(BUILD_PROPERTIES, {})

        if metadata and dependency_manager and dependency_manager == "npm-esbuild":
            # Esbuild takes an array of entry points from which to start bundling
            # as a required argument. This corresponds to the lambda function handler.
            normalized_build_props = ResourceMetadataNormalizer.normalize_build_properties(build_props)
            if handler and not build_props.get("EntryPoints"):
                entry_points = [handler.split(".")[0]]
                normalized_build_props["entry_points"] = entry_points
            return normalized_build_props

        _build_options: Dict = {
            "go": {"artifact_executable_name": handler},
            "provided": {"build_logical_id": function_name},
            "nodejs": {"use_npm_ci": build_props.get("UseNpmCi", False)},
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
        architecture: str,
        options: Optional[Dict],
        dependencies_dir: Optional[str],
        download_dependencies: bool,
        combine_dependencies: bool,
        is_building_layer: bool = False,
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
                architecture=architecture,
                dependencies_dir=dependencies_dir,
                download_dependencies=download_dependencies,
                combine_dependencies=combine_dependencies,
                is_building_layer=is_building_layer,
                experimental_flags=get_enabled_experimental_flags(),
            )
        except LambdaBuilderError as ex:
            raise BuildError(wrapped_from=ex.__class__.__name__, msg=str(ex)) from ex

        return artifacts_dir

    def _build_function_on_container(
        self,  # pylint: disable=too-many-locals
        config: CONFIG,
        source_dir: str,
        artifacts_dir: str,
        manifest_path: str,
        runtime: str,
        architecture: str,
        options: Optional[Dict],
        container_env_vars: Optional[Dict] = None,
        build_image: Optional[str] = None,
        is_building_layer: bool = False,
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

        container_env_vars = container_env_vars or {}

        container = LambdaBuildContainer(
            lambda_builders_protocol_version,
            config.language,
            config.dependency_manager,
            config.application_framework,
            source_dir,
            manifest_path,
            runtime,
            architecture,
            log_level=log_level,
            optimizations=None,
            options=options,
            executable_search_paths=config.executable_search_paths,
            mode=self._mode,
            env_vars=container_env_vars,
            image=build_image,
            is_building_layer=is_building_layer,
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

    @staticmethod
    def _make_env_vars(
        resource: Union[Function, LayerVersion], file_env_vars: Dict, inline_env_vars: Optional[Dict]
    ) -> Dict:
        """Returns the environment variables configuration for this function

        Priority order (high to low):
        1. Function specific env vars from command line
        2. Function specific env vars from json file
        3. Global env vars from command line
        4. Global env vars from json file

        Parameters
        ----------
        resource : Union[Function, LayerVersion]
            Lambda function or layer to generate the configuration for
        file_env_vars : Dict
            The dictionary of environment variables loaded from the file
        inline_env_vars : Optional[Dict]
            The optional dictionary of environment variables defined inline


        Returns
        -------
        dictionary
            Environment variable configuration for this function

        Raises
        ------
        samcli.commands.local.lib.exceptions.OverridesNotWellDefinedError
            If the environment dict is in the wrong format to process environment vars

        """

        name = resource.name
        result = {}

        # validate and raise OverridesNotWellDefinedError
        for env_var in list((file_env_vars or {}).values()) + list((inline_env_vars or {}).values()):
            if not isinstance(env_var, dict):
                reason = "Environment variables {} in incorrect format".format(env_var)
                LOG.debug(reason)
                raise OverridesNotWellDefinedError(reason)

        if file_env_vars:
            parameter_result = file_env_vars.get("Parameters", {})
            result.update(parameter_result)

        if inline_env_vars:
            inline_parameter_result = inline_env_vars.get("Parameters", {})
            result.update(inline_parameter_result)

        if file_env_vars:
            specific_result = file_env_vars.get(name, {})
            result.update(specific_result)

        if inline_env_vars:
            inline_specific_result = inline_env_vars.get(name, {})
            result.update(inline_specific_result)

        return result
