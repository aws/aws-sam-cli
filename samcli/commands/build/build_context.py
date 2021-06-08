"""
Context object used by build command
"""

import logging
import os
import pathlib
import shutil
from typing import Dict, Optional, List

from samcli.commands.build.exceptions import InvalidBuildDirException, MissingBuildMethodException
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.providers.provider import ResourcesToBuildCollector, Stack, Function, LayerVersion
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_layer_provider import SamLayerProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.local.docker.manager import ContainerManager
from samcli.local.lambdafn.exceptions import ResourceNotFound

LOG = logging.getLogger(__name__)


class BuildContext:
    # Build directories need not be world writable.
    # This is usually a optimal permission for directories
    _BUILD_DIR_PERMISSIONS = 0o755

    def __init__(
        self,
        resource_identifier: Optional[str],
        template_file: str,
        base_dir: Optional[str],
        build_dir: str,
        cache_dir: str,
        cached: bool,
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
        aws_region: Optional[str] = None,
    ) -> None:

        self._resource_identifier = resource_identifier
        self._template_file = template_file
        self._base_dir = base_dir

        # Note(xinhol): use_raw_codeuri is temporary to fix a bug, and will be removed for a permanent solution.
        self._use_raw_codeuri = bool(self._base_dir)

        self._build_dir = build_dir
        self._cache_dir = cache_dir
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

        self._function_provider: Optional[SamFunctionProvider] = None
        self._layer_provider: Optional[SamLayerProvider] = None
        self._container_manager: Optional[ContainerManager] = None
        self._stacks: List[Stack] = []

    def __enter__(self) -> "BuildContext":

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
        self._function_provider = SamFunctionProvider(self.stacks, self._use_raw_codeuri)
        self._layer_provider = SamLayerProvider(self.stacks, self._use_raw_codeuri)

        if not self._base_dir:
            # Base directory, if not provided, is the directory containing the template
            self._base_dir = str(pathlib.Path(self._template_file).resolve().parent)

        self._build_dir = self._setup_build_dir(self._build_dir, self._clean)

        if self._cached:
            cache_path = pathlib.Path(self._cache_dir)
            cache_path.mkdir(mode=self._BUILD_DIR_PERMISSIONS, parents=True, exist_ok=True)
            self._cache_dir = str(cache_path.resolve())

        if self._use_container:
            self._container_manager = ContainerManager(
                docker_network_id=self._docker_network, skip_pull_image=self._skip_pull_image
            )

        return self

    def __exit__(self, *args):
        pass

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

        build_path.mkdir(mode=BuildContext._BUILD_DIR_PERMISSIONS, parents=True, exist_ok=True)

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
    def resources_to_build(self) -> ResourcesToBuildCollector:
        """
        Function return resources that should be build by current build command. This function considers
        Lambda Functions and Layers with build method as buildable resources.
        Returns
        -------
        ResourcesToBuildCollector
        """
        result = ResourcesToBuildCollector()
        if self._resource_identifier:
            self._collect_single_function_and_dependent_layers(self._resource_identifier, result)
            self._collect_single_buildable_layer(self._resource_identifier, result)

            if not result.functions and not result.layers:
                all_resources = [f.name for f in self.function_provider.get_all() if not f.inlinecode]
                all_resources.extend([l.name for l in self.layer_provider.get_all()])

                available_resource_message = (
                    f"{self._resource_identifier} not found. Possible options in your " f"template: {all_resources}"
                )
                LOG.info(available_resource_message)
                raise ResourceNotFound(f"Unable to find a function or layer with name '{self._resource_identifier}'")
            return result
        result.add_functions([f for f in self.function_provider.get_all() if BuildContext._is_function_buildable(f)])
        result.add_layers([l for l in self.layer_provider.get_all() if BuildContext._is_layer_buildable(l)])
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
        resource_collector.add_layers([l for l in function.layers if l.build_method is not None])

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
        return True
