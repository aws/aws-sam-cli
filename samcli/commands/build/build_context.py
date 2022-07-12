"""
Context object used by build command
"""
import logging
import os
import pathlib
import shutil
from typing import Dict, Optional, List, Tuple, cast

import click

from samcli.commands._utils.experimental import ExperimentalFlag, prompt_experimental
from samcli.lib.providers.sam_api_provider import SamApiProvider
from samcli.lib.utils.packagetype import IMAGE

from samcli.commands._utils.template import get_template_data
from samcli.commands.build.exceptions import InvalidBuildDirException, MissingBuildMethodException
from samcli.lib.bootstrap.nested_stack.nested_stack_manager import NestedStackManager
from samcli.lib.build.build_graph import DEFAULT_DEPENDENCIES_DIR
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.providers.provider import ResourcesToBuildCollector, Stack, Function, LayerVersion
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_layer_provider import SamLayerProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.osutils import BUILD_DIR_PERMISSIONS
from samcli.local.docker.manager import ContainerManager
from samcli.local.lambdafn.exceptions import ResourceNotFound
from samcli.lib.build.exceptions import BuildInsideContainerError

from samcli.commands.exceptions import UserException

from samcli.lib.build.app_builder import (
    ApplicationBuilder,
    BuildError,
    UnsupportedBuilderLibraryVersionError,
    ContainerBuildNotSupported,
)
from samcli.commands._utils.options import DEFAULT_BUILD_DIR
from samcli.lib.build.workflow_config import UnsupportedRuntimeException
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.commands._utils.template import move_template
from samcli.lib.build.exceptions import InvalidBuildGraphException

LOG = logging.getLogger(__name__)


class BuildContext:
    def __init__(
        self,
        resource_identifier: Optional[str],
        template_file: str,
        base_dir: Optional[str],
        build_dir: str,
        cache_dir: str,
        cached: bool,
        parallel: bool,
        mode: Optional[str],
        manifest_path: Optional[str] = None,
        clean: bool = False,
        use_container: bool = False,
        # pylint: disable=fixme
        # FIXME: parameter_overrides is never None, we should change this to "dict" from Optional[dict]
        # See samcli/commands/_utils/options.py:251 for its all possible values
        parameter_overrides: Optional[dict] = None,
        docker_network: Optional[str] = None,
        skip_pull_image: bool = False,
        container_env_var: Optional[dict] = None,
        container_env_var_file: Optional[str] = None,
        build_images: Optional[dict] = None,
        excluded_resources: Optional[Tuple[str, ...]] = None,
        aws_region: Optional[str] = None,
        create_auto_dependency_layer: bool = False,
        stack_name: Optional[str] = None,
        print_success_message: bool = True,
        locate_layer_nested: bool = False,
    ) -> None:
        """
        Initialize the class

        Parameters
        ----------
        resource_identifier: Optional[str]
            The unique identifier of the resource
        template_file: str
            Path to the template for building
        base_dir : str
            Path to a folder. Use this folder as the root to resolve relative source code paths against
        build_dir : str
            Path to the directory where we will be storing built artifacts
        cache_dir : str
            Path to a the directory where we will be caching built artifacts
        cached:
            Optional. Set to True to build each function with cache to improve performance
        parallel : bool
            Optional. Set to True to build each function in parallel to improve performance
        mode : str
            Optional, name of the build mode to use ex: 'debug'
        manifest_path : Optional[str]
            Optional path to manifest file to replace the default one
        clean: bool
            Clear the build directory before building
        use_container: bool
            Build inside container
        parameter_overrides: Optional[dict]
            Optional dictionary of values for SAM template parameters that might want
            to get substituted within the template
        docker_network: Optional[str]
            Docker network to run the container in.
        skip_pull_image: bool
            Whether we should pull new Docker container image or not
        container_env_var: Optional[dict]
            An optional dictionary of environment variables to pass to the container
        container_env_var_file: Optional[dict]
            An optional path to file that contains environment variables to pass to the container
        build_images: Optional[dict]
            An optional dictionary of build images to be used for building functions
        aws_region: Optional[str]
            Aws region code
        create_auto_dependency_layer: bool
            Create auto dependency layer for accelerate feature
        stack_name: Optional[str]
            Original stack name, which is used to generate layer name for accelerate feature
        print_success_message: bool
            Print successful message
        locate_layer_nested: bool
            Locate layer to its actual, worked with nested stack
        """

        self._resource_identifier = resource_identifier
        self._template_file = template_file
        self._base_dir = base_dir

        # Note(xinhol): use_raw_codeuri is temporary to fix a bug, and will be removed for a permanent solution.
        self._use_raw_codeuri = bool(self._base_dir)

        self._build_dir = build_dir
        self._cache_dir = cache_dir
        self._parallel = parallel
        self._manifest_path = manifest_path
        self._clean = clean
        self._use_container = use_container
        self._parameter_overrides = parameter_overrides
        # Override certain CloudFormation pseudo-parameters based on values provided by customer
        self._global_parameter_overrides: Optional[Dict] = None
        if aws_region:
            self._global_parameter_overrides = {IntrinsicsSymbolTable.AWS_REGION: aws_region}
        self._docker_network = docker_network
        self._skip_pull_image = skip_pull_image
        self._mode = mode
        self._cached = cached
        self._container_env_var = container_env_var
        self._container_env_var_file = container_env_var_file
        self._build_images = build_images
        self._exclude = excluded_resources
        self._create_auto_dependency_layer = create_auto_dependency_layer
        self._stack_name = stack_name
        self._print_success_message = print_success_message

        self._function_provider: Optional[SamFunctionProvider] = None
        self._layer_provider: Optional[SamLayerProvider] = None
        self._container_manager: Optional[ContainerManager] = None
        self._stacks: List[Stack] = []
        self._locate_layer_nested = locate_layer_nested

    def __enter__(self) -> "BuildContext":
        self.set_up()
        return self

    def set_up(self) -> None:
        """Set up class members used for building
        This should be called each time before run() if stacks are changed."""
        self._stacks, remote_stack_full_paths = SamLocalStackProvider.get_stacks(
            self._template_file,
            parameter_overrides=self._parameter_overrides,
            global_parameter_overrides=self._global_parameter_overrides,
        )

        if remote_stack_full_paths:
            LOG.warning(
                "Below nested stacks(s) specify non-local URL(s), which are unsupported:\n%s\n"
                "Skipping building resources inside these nested stacks.",
                "\n".join([f"- {full_path}" for full_path in remote_stack_full_paths]),
            )

        # Note(xinhol): self._use_raw_codeuri is added temporarily to fix issue #2717
        # when base_dir is provided, codeuri should not be resolved based on template file path.
        # we will refactor to make all path resolution inside providers intead of in multiple places
        self._function_provider = SamFunctionProvider(
            self.stacks, self._use_raw_codeuri, locate_layer_nested=self._locate_layer_nested
        )
        self._layer_provider = SamLayerProvider(self.stacks, self._use_raw_codeuri)

        if not self._base_dir:
            # Base directory, if not provided, is the directory containing the template
            self._base_dir = str(pathlib.Path(self._template_file).resolve().parent)

        self._build_dir = self._setup_build_dir(self._build_dir, self._clean)

        if self._cached:
            cache_path = pathlib.Path(self._cache_dir)
            cache_path.mkdir(mode=BUILD_DIR_PERMISSIONS, parents=True, exist_ok=True)
            self._cache_dir = str(cache_path.resolve())

            dependencies_path = pathlib.Path(DEFAULT_DEPENDENCIES_DIR)
            dependencies_path.mkdir(mode=BUILD_DIR_PERMISSIONS, parents=True, exist_ok=True)
        if self._use_container:
            self._container_manager = ContainerManager(
                docker_network_id=self._docker_network, skip_pull_image=self._skip_pull_image
            )

    def __exit__(self, *args):
        pass

    def get_resources_to_build(self):
        return self.resources_to_build

    def run(self):
        """Runs the building process by creating an ApplicationBuilder."""
        template_dict = get_template_data(self._template_file)
        template_transform = template_dict.get("Transform", "")
        is_sam_template = isinstance(template_transform, str) and template_transform.startswith("AWS::Serverless")
        if is_sam_template:
            SamApiProvider.check_implicit_api_resource_ids(self.stacks)

        try:
            builder = ApplicationBuilder(
                self.get_resources_to_build(),
                self.build_dir,
                self.base_dir,
                self.cache_dir,
                self.cached,
                self.is_building_specific_resource,
                manifest_path_override=self.manifest_path_override,
                container_manager=self.container_manager,
                mode=self.mode,
                parallel=self._parallel,
                container_env_var=self._container_env_var,
                container_env_var_file=self._container_env_var_file,
                build_images=self._build_images,
                combine_dependencies=not self._create_auto_dependency_layer,
            )
        except FunctionNotFound as ex:
            raise UserException(str(ex), wrapped_from=ex.__class__.__name__) from ex

        try:
            self._check_esbuild_warning()
            self._check_exclude_warning()
            build_result = builder.build()
            artifacts = build_result.artifacts

            stack_output_template_path_by_stack_path = {
                stack.stack_path: stack.get_output_template_path(self.build_dir) for stack in self.stacks
            }
            for stack in self.stacks:
                modified_template = builder.update_template(
                    stack,
                    artifacts,
                    stack_output_template_path_by_stack_path,
                )
                output_template_path = stack.get_output_template_path(self.build_dir)

                if self._create_auto_dependency_layer:
                    LOG.debug("Auto creating dependency layer for each function resource into a nested stack")
                    nested_stack_manager = NestedStackManager(
                        stack, self._stack_name, self.build_dir, modified_template, build_result
                    )
                    modified_template = nested_stack_manager.generate_auto_dependency_layer_stack()
                move_template(stack.location, output_template_path, modified_template)

            click.secho("\nBuild Succeeded", fg="green")

            # try to use relpath so the command is easier to understand, however,
            # under Windows, when SAM and (build_dir or output_template_path) are
            # on different drive, relpath() fails.
            root_stack = SamLocalStackProvider.find_root_stack(self.stacks)
            out_template_path = root_stack.get_output_template_path(self.build_dir)
            try:
                build_dir_in_success_message = os.path.relpath(self.build_dir)
                output_template_path_in_success_message = os.path.relpath(out_template_path)
            except ValueError:
                LOG.debug("Failed to retrieve relpath - using the specified path as-is instead")
                build_dir_in_success_message = self.build_dir
                output_template_path_in_success_message = out_template_path

            if self._print_success_message:
                msg = self.gen_success_msg(
                    build_dir_in_success_message,
                    output_template_path_in_success_message,
                    os.path.abspath(self.build_dir) == os.path.abspath(DEFAULT_BUILD_DIR),
                )

                click.secho(msg, fg="yellow")

        except (
            UnsupportedRuntimeException,
            BuildError,
            BuildInsideContainerError,
            UnsupportedBuilderLibraryVersionError,
            ContainerBuildNotSupported,
            InvalidBuildGraphException,
        ) as ex:
            click.secho("\nBuild Failed", fg="red")

            # Some Exceptions have a deeper wrapped exception that needs to be surfaced
            # from deeper than just one level down.
            deep_wrap = getattr(ex, "wrapped_from", None)
            wrapped_from = deep_wrap if deep_wrap else ex.__class__.__name__
            raise UserException(str(ex), wrapped_from=wrapped_from) from ex

    @staticmethod
    def gen_success_msg(artifacts_dir: str, output_template_path: str, is_default_build_dir: bool) -> str:

        invoke_cmd = "sam local invoke"
        if not is_default_build_dir:
            invoke_cmd += " -t {}".format(output_template_path)

        deploy_cmd = "sam deploy --guided"
        if not is_default_build_dir:
            deploy_cmd += " --template-file {}".format(output_template_path)

        msg = """\nBuilt Artifacts  : {artifacts_dir}
Built Template   : {template}

Commands you can use next
=========================
[*] Validate SAM template: sam validate
[*] Invoke Function: {invokecmd}
[*] Test Function in the Cloud: sam sync --stack-name {{stack-name}} --watch
[*] Deploy: {deploycmd}
        """.format(
            invokecmd=invoke_cmd, deploycmd=deploy_cmd, artifacts_dir=artifacts_dir, template=output_template_path
        )

        return msg

    @staticmethod
    def _setup_build_dir(build_dir: str, clean: bool) -> str:
        build_path = pathlib.Path(build_dir)

        if os.path.abspath(str(build_path)) == os.path.abspath(str(pathlib.Path.cwd())):
            exception_message = (
                "Failing build: Running a build with build-dir as current working directory "
                "is extremely dangerous since the build-dir contents is first removed. "
                "This is no longer supported, please remove the '--build-dir' option from the command "
                "to allow the build artifacts to be placed in the directory your template is in."
            )
            raise InvalidBuildDirException(exception_message)

        if build_path.exists() and os.listdir(build_dir) and clean:
            # build folder contains something inside. Clear everything.
            shutil.rmtree(build_dir)

        build_path.mkdir(mode=BUILD_DIR_PERMISSIONS, parents=True, exist_ok=True)

        # ensure path resolving is done after creation: https://bugs.python.org/issue32434
        return str(build_path.resolve())

    @property
    def container_manager(self) -> Optional[ContainerManager]:
        return self._container_manager

    @property
    def function_provider(self) -> SamFunctionProvider:
        # Note(xinhol): despite self._function_provider is Optional
        # self._function_provider will be assigned with a non-None value in __enter__() and
        # this function is only used in the context (after __enter__ is called)
        # so we can assume it is not Optional here
        return self._function_provider  # type: ignore

    @property
    def layer_provider(self) -> SamLayerProvider:
        # same as function_provider()
        return self._layer_provider  # type: ignore

    @property
    def build_dir(self) -> str:
        return self._build_dir

    @property
    def base_dir(self) -> str:
        # Note(xinhol): self._base_dir will be assigned with a str value if it is None in __enter__()
        return self._base_dir  # type: ignore

    @property
    def cache_dir(self) -> str:
        return self._cache_dir

    @property
    def cached(self) -> bool:
        return self._cached

    @property
    def use_container(self) -> bool:
        return self._use_container

    @property
    def stacks(self) -> List[Stack]:
        return self._stacks

    @property
    def manifest_path_override(self) -> Optional[str]:
        if self._manifest_path:
            return os.path.abspath(self._manifest_path)

        return None

    @property
    def mode(self) -> Optional[str]:
        return self._mode

    @property
    def use_base_dir(self) -> bool:
        return self._use_raw_codeuri

    @property
    def resources_to_build(self) -> ResourcesToBuildCollector:
        """
        Function return resources that should be build by current build command. This function considers
        Lambda Functions and Layers with build method as buildable resources.
        Returns
        -------
        ResourcesToBuildCollector
        """
        return (
            self.collect_build_resources(self._resource_identifier)
            if self._resource_identifier
            else self.collect_all_build_resources()
        )

    @property
    def create_auto_dependency_layer(self) -> bool:
        return self._create_auto_dependency_layer

    def collect_build_resources(self, resource_identifier: str) -> ResourcesToBuildCollector:
        """Collect a single buildable resource and its dependencies.
        For a Lambda function, its layers will be included.

        Parameters
        ----------
        resource_identifier : str
            Resource identifier for the resource to be built

        Returns
        -------
        ResourcesToBuildCollector
            ResourcesToBuildCollector containing the buildable resource and its dependencies

        Raises
        ------
        ResourceNotFound
            raises ResourceNotFound is the specified resource cannot be found.
        """
        result = ResourcesToBuildCollector()
        # Get the functions and its layer. Skips if it's inline.
        self._collect_single_function_and_dependent_layers(resource_identifier, result)
        self._collect_single_buildable_layer(resource_identifier, result)

        if not result.functions and not result.layers:
            # Collect all functions and layers that are not inline
            all_resources = [f.name for f in self.function_provider.get_all() if not f.inlinecode]
            all_resources.extend([l.name for l in self.layer_provider.get_all()])

            available_resource_message = (
                f"{resource_identifier} not found. Possible options in your " f"template: {all_resources}"
            )
            LOG.info(available_resource_message)
            raise ResourceNotFound(f"Unable to find a function or layer with name '{resource_identifier}'")
        return result

    def collect_all_build_resources(self) -> ResourcesToBuildCollector:
        """Collect all buildable resources. Including Lambda functions and layers.

        Returns
        -------
        ResourcesToBuildCollector
            ResourcesToBuildCollector that contains all the buildable resources.
        """
        result = ResourcesToBuildCollector()
        excludes: Tuple[str, ...] = self._exclude if self._exclude is not None else ()
        result.add_functions(
            [
                f
                for f in self.function_provider.get_all()
                if (f.name not in excludes) and BuildContext._is_function_buildable(f)
            ]
        )
        result.add_layers(
            [
                l
                for l in self.layer_provider.get_all()
                if (l.name not in excludes) and BuildContext._is_layer_buildable(l)
            ]
        )
        return result

    @property
    def is_building_specific_resource(self) -> bool:
        """
        Whether customer requested to build a specific resource alone in isolation,
        by specifying function_identifier to the build command.
        Ex: sam build MyServerlessFunction
        :return: True if user requested to build specific resource, False otherwise
        """
        return bool(self._resource_identifier)

    def _collect_single_function_and_dependent_layers(
        self, resource_identifier: str, resource_collector: ResourcesToBuildCollector
    ) -> None:
        """
        Populate resource_collector with function with provided identifier and all layers that function need to be
        build in resource_collector
        Parameters
        ----------
        resource_collector: Collector that will be populated with resources.
        """
        function = self.function_provider.get(resource_identifier)
        if not function:
            # No function found
            return

        resource_collector.add_function(function)
        resource_collector.add_layers([l for l in function.layers if l.build_method is not None and not l.skip_build])

    def _collect_single_buildable_layer(
        self, resource_identifier: str, resource_collector: ResourcesToBuildCollector
    ) -> None:
        """
        Populate resource_collector with layer with provided identifier.

        Parameters
        ----------
        resource_collector

        Returns
        -------

        """
        layer = self.layer_provider.get(resource_identifier)
        if not layer:
            # No layer found
            return
        if layer and layer.build_method is None:
            LOG.error("Layer %s is missing BuildMethod Metadata.", self._function_provider)
            raise MissingBuildMethodException(f"Build method missing in layer {resource_identifier}.")

        resource_collector.add_layer(layer)

    @staticmethod
    def _is_function_buildable(function: Function):
        # no need to build inline functions
        if function.inlinecode:
            LOG.debug("Skip building inline function: %s", function.full_path)
            return False
        # no need to build functions that are already packaged as a zip file
        if isinstance(function.codeuri, str) and function.codeuri.endswith(".zip"):
            LOG.debug("Skip building zip function: %s", function.full_path)
            return False
        # skip build the functions that marked as skip-build
        if function.skip_build:
            LOG.debug("Skip building pre-built function: %s", function.full_path)
            return False
        # skip build the functions with Image Package Type with no docker context or docker file metadata
        if function.packagetype == IMAGE:
            metadata = function.metadata if function.metadata else {}
            dockerfile = cast(str, metadata.get("Dockerfile", ""))
            docker_context = cast(str, metadata.get("DockerContext", ""))
            if not dockerfile or not docker_context:
                LOG.debug(
                    "Skip Building %s function, as it is missing either Dockerfile or DockerContext "
                    "metadata properties.",
                    function.full_path,
                )
                return False
        return True

    @staticmethod
    def _is_layer_buildable(layer: LayerVersion):
        # if build method is not specified, it is not buildable
        if not layer.build_method:
            LOG.debug("Skip building layer without a build method: %s", layer.full_path)
            return False
        # no need to build layers that are already packaged as a zip file
        if isinstance(layer.codeuri, str) and layer.codeuri.endswith(".zip"):
            LOG.debug("Skip building zip layer: %s", layer.full_path)
            return False
        # skip build the functions that marked as skip-build
        if layer.skip_build:
            LOG.debug("Skip building pre-built layer: %s", layer.full_path)
            return False
        return True

    _ESBUILD_WARNING_MESSAGE = (
        "Using esbuild for bundling Node.js and TypeScript is a beta feature.\n"
        "Please confirm if you would like to proceed with using esbuild to build your function.\n"
        "You can also enable this beta feature with 'sam build --beta-features'."
    )

    _EXCLUDE_WARNING_MESSAGE = "Resource expected to be built, but marked as excluded.\nBuilding anyways..."

    def _check_esbuild_warning(self) -> None:
        """
        Prints warning message and confirms that the user wants to enable beta features
        """
        resources_to_build = self.get_resources_to_build()
        is_building_esbuild = False
        for function in resources_to_build.functions:
            if function.metadata and function.metadata.get("BuildMethod", "") == "esbuild":
                is_building_esbuild = True
                break

        if is_building_esbuild:
            prompt_experimental(ExperimentalFlag.Esbuild, self._ESBUILD_WARNING_MESSAGE)

    def _check_exclude_warning(self) -> None:
        """
        Prints warning message if a single resource to build is also being excluded
        """
        excludes: Tuple[str, ...] = self._exclude if self._exclude is not None else ()
        if self._resource_identifier in excludes:
            LOG.warning(self._EXCLUDE_WARNING_MESSAGE)
