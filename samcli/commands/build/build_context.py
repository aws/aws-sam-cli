"""
Context object used by build command
"""

import logging
import os
import shutil
import pathlib

from samcli.lib.providers.provider import ResourcesToBuildCollector
from samcli.local.docker.manager import ContainerManager
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_layer_provider import SamLayerProvider
from samcli.commands._utils.template import get_template_data
from samcli.local.lambdafn.exceptions import ResourceNotFound
from samcli.commands.build.exceptions import InvalidBuildDirException, MissingBuildMethodException

LOG = logging.getLogger(__name__)


class BuildContext:
    # Build directories need not be world writable.
    # This is usually a optimal permission for directories
    _BUILD_DIR_PERMISSIONS = 0o755

    def __init__(
            self,
            resource_identifier,
            template_file,
            base_dir,
            build_dir,
            cache_dir,
            cached,
            mode,
            manifest_path=None,
            clean=False,
            use_container=False,
            parameter_overrides=None,
            docker_network=None,
            skip_pull_image=False,
    ):

        self._resource_identifier = resource_identifier
        self._template_file = template_file
        self._base_dir = base_dir
        self._build_dir = build_dir
        self._cache_dir = cache_dir
        self._manifest_path = manifest_path
        self._clean = clean
        self._use_container = use_container
        self._parameter_overrides = parameter_overrides
        self._docker_network = docker_network
        self._skip_pull_image = skip_pull_image
        self._mode = mode
        self._cached = cached

        self._function_provider = None
        self._layer_provider = None
        self._template_dict = None
        self._app_builder = None
        self._container_manager = None

    def __enter__(self):
        self._template_dict = get_template_data(self._template_file)

        self._function_provider = SamFunctionProvider(self._template_dict, self._parameter_overrides)
        self._layer_provider = SamLayerProvider(self._template_dict, self._parameter_overrides)

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
    def _setup_build_dir(build_dir, clean):
        build_path = pathlib.Path(build_dir)

        if os.path.abspath(str(build_path)) == os.path.abspath(str(pathlib.Path.cwd())):
            exception_message = "Failing build: Running a build with build-dir as current working directory is extremely dangerous since the build-dir contents is first removed. This is no longer supported, please remove the '--build-dir' option from the command to allow the build artifacts to be placed in the directory your template is in."
            raise InvalidBuildDirException(exception_message)

        if build_path.exists() and os.listdir(build_dir) and clean:
            # build folder contains something inside. Clear everything.
            shutil.rmtree(build_dir)

        build_path.mkdir(mode=BuildContext._BUILD_DIR_PERMISSIONS, parents=True, exist_ok=True)

        # ensure path resolving is done after creation: https://bugs.python.org/issue32434
        return str(build_path.resolve())

    @property
    def container_manager(self):
        return self._container_manager

    @property
    def function_provider(self):
        return self._function_provider

    @property
    def layer_provider(self):
        return self._layer_provider

    @property
    def template_dict(self):
        return self._template_dict

    @property
    def build_dir(self):
        return self._build_dir

    @property
    def base_dir(self):
        return self._base_dir

    @property
    def cache_dir(self):
        return self._cache_dir

    @property
    def cached(self):
        return self._cached

    @property
    def use_container(self):
        return self._use_container

    @property
    def output_template_path(self):
        return os.path.join(self._build_dir, "template.yaml")

    @property
    def original_template_path(self):
        return os.path.abspath(self._template_file)

    @property
    def manifest_path_override(self):
        if self._manifest_path:
            return os.path.abspath(self._manifest_path)

        return None

    @property
    def mode(self):
        return self._mode

    @property
    def resources_to_build(self):
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
                all_resources = [f.name for f in self._function_provider.get_all()]
                all_resources.extend([l.name for l in self._layer_provider.get_all()])

                available_resource_message = f"{self._resource_identifier} not found. Possible options in your " \
                                             f"template: {all_resources}"
                LOG.info(available_resource_message)
                raise ResourceNotFound(f"Unable to find a function or layer with name '{self._resource_identifier}'")
            return result
        result.add_functions(self._function_provider.get_all())
        result.add_layers([l for l in self._layer_provider.get_all() if l.build_method is not None])
        return result

    @property
    def is_building_specific_resource(self):
        """
        Whether customer requested to build a specific resource alone in isolation,
        by specifying function_identifier to the build command.
        Ex: sam build MyServerlessFunction
        :return: True if user requested to build specific resource, False otherwise
        """
        return bool(self._resource_identifier)

    def _collect_single_function_and_dependent_layers(self, resource_identifier, resource_collector):
        """
        Populate resource_collector with function with provided identifier and all layers that function need to be
        build in resource_collector
        Parameters
        ----------
        resource_collector: Collector that will be populated with resources.

        Returns
        -------
        ResourcesToBuildCollector

        """
        function = self._function_provider.get(resource_identifier)
        if not function:
            # No function found
            return

        resource_collector.add_function(function)
        resource_collector.add_layers([l for l in function.layers if l.build_method is not None])

    def _collect_single_buildable_layer(self, resource_identifier, resource_collector):
        """
        Populate resource_collector with layer with provided identifier.

        Parameters
        ----------
        resource_collector

        Returns
        -------

        """
        layer = self._layer_provider.get(resource_identifier)
        if not layer:
            # No layer found
            return
        if layer and layer.build_method is None:
            LOG.error("Layer %s is missing BuildMethod Metadata.", self._function_provider)
            raise MissingBuildMethodException(f"Build method missing in layer {resource_identifier}.")

        resource_collector.add_layer(layer)
