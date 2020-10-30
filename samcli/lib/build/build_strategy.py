"""
Keeps implementation of different build strategies
"""
import logging
import pathlib
import shutil

from samcli.commands.build.exceptions import MissingBuildMethodException
from samcli.lib.utils import osutils
from samcli.lib.utils.async_utils import AsyncContext
from samcli.lib.utils.hash import dir_checksum

LOG = logging.getLogger(__name__)


class BuildStrategy:
    """
    Base class for BuildStrategy
    Keeps basic implementation of build, build_functions and build_layers
    """

    def __init__(self, build_graph):
        self._build_graph = build_graph

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def build(self):
        """
        Builds all functions and layers in the given build graph
        """
        result = {}
        with self:
            result.update(self._build_functions(self._build_graph))
            result.update(self._build_layers(self._build_graph))

        return result

    def _build_functions(self, build_graph):
        """
        Iterates through build graph and runs each unique build and copies outcome to the corresponding function folder
        """
        function_build_results = {}
        for build_definition in build_graph.get_function_build_definitions():
            function_build_results.update(self.build_single_function_definition(build_definition))

        return function_build_results

    def build_single_function_definition(self, build_definition):
        """
        Builds single function definition and returns dictionary which contains function name as key,
        build location as value
        """
        return {}

    def _build_layers(self, build_graph):
        """
        Iterates through build graph and runs each unique build and copies outcome to the corresponding layer folder
        """
        layer_build_results = {}
        for layer_definition in build_graph.get_layer_build_definitions():
            layer_build_results.update(self.build_single_layer_definition(layer_definition))

        return layer_build_results

    def build_single_layer_definition(self, layer_definition):
        """
        Builds single layer definition and returns dictionary which contains layer name as key,
        build location as value
        """
        return {}


class DefaultBuildStrategy(BuildStrategy):
    """
    Default build strategy, loops over given build graph for each function and layer, and builds each of them one by one
    """

    def __init__(self, build_graph, build_dir, build_function, build_layer):
        super().__init__(build_graph)
        self._build_dir = build_dir
        self._build_function = build_function
        self._build_layer = build_layer

    def build_single_function_definition(self, build_definition):
        """
        Build the unique definition and then copy the artifact to the corresponding function folder
        """
        function_build_results = {}
        LOG.info("Building codeuri: %s runtime: %s metadata: %s functions: %s",
                 build_definition.codeuri,
                 build_definition.runtime,
                 build_definition.metadata,
                 [function.name for function in build_definition.functions])

        # build into one of the functions from this build definition
        single_function_name = build_definition.get_function_name()
        single_build_dir = str(pathlib.Path(self._build_dir, single_function_name))

        LOG.debug("Building to following folder %s", single_build_dir)
        self._build_function(build_definition.get_function_name(),
                             build_definition.codeuri,
                             build_definition.runtime,
                             build_definition.get_handler_name(),
                             single_build_dir,
                             build_definition.metadata)
        function_build_results[single_function_name] = single_build_dir

        # copy results to other functions
        for function in build_definition.functions:
            if function.name is not single_function_name:
                # artifacts directory will be created by the builder
                artifacts_dir = str(pathlib.Path(self._build_dir, function.name))
                LOG.debug("Copying artifacts from %s to %s", single_build_dir, artifacts_dir)
                osutils.copytree(single_build_dir, artifacts_dir)
                function_build_results[function.name] = artifacts_dir

        return function_build_results

    def build_single_layer_definition(self, layer_definition):
        """
        Build the unique definition and then copy the artifact to the corresponding layer folder
        """
        layer = layer_definition.layer
        LOG.info("Building layer '%s'", layer.name)
        if layer.build_method is None:
            raise MissingBuildMethodException(
                f"Layer {layer.name} cannot be build without BuildMethod. Please provide BuildMethod in Metadata.")
        return {layer.name: self._build_layer(layer.name,
                                              layer.codeuri,
                                              layer.build_method,
                                              layer.compatible_runtimes)}


class CachedBuildStrategy(BuildStrategy):
    """
    Cached implementation of Build Strategy
    For each function and layer, it first checks if there is a valid cache, and if there is, it copies from previous
    build. If caching is invalid, it builds function or layer from scratch and updates cache folder and md5 of the
    function or layer.
    For actual building, it uses delegate implementation
    """

    def __init__(self, build_graph, delegate_build_strategy, base_dir, build_dir, cache_dir,
                 is_building_specific_resource):
        super().__init__(build_graph)
        self._delegate_build_strategy = delegate_build_strategy
        self._base_dir = base_dir
        self._build_dir = build_dir
        self._cache_dir = cache_dir
        self._is_building_specific_resource = is_building_specific_resource

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._clean_redundant_cached()

    def build(self):
        result = {}
        with self, self._delegate_build_strategy:
            result.update(super().build())
        return result

    def build_single_function_definition(self, build_definition):
        """
        Builds single function definition with caching
        """
        code_dir = str(pathlib.Path(self._base_dir, build_definition.codeuri).resolve())
        source_md5 = dir_checksum(code_dir)
        cache_function_dir = pathlib.Path(self._cache_dir, build_definition.uuid)
        function_build_results = {}

        if not cache_function_dir.exists() or build_definition.source_md5 != source_md5:
            LOG.info("Cache is invalid, running build and copying resources to function build definition of %s",
                     build_definition.uuid)
            build_result = self._delegate_build_strategy.build_single_function_definition(build_definition)
            function_build_results.update(build_result)

            if cache_function_dir.exists():
                shutil.rmtree(str(cache_function_dir))

            build_definition.source_md5 = source_md5
            # Since all the build contents are same for a build definition, just copy any one of them into the cache
            for _, value in build_result.items():
                osutils.copytree(value, cache_function_dir)
                break
        else:
            LOG.info("Valid cache found, copying previously built resources from function build definition of %s",
                     build_definition.uuid)
            for function in build_definition.functions:
                # artifacts directory will be created by the builder
                artifacts_dir = str(pathlib.Path(self._build_dir, function.name))
                LOG.debug("Copying artifacts from %s to %s", cache_function_dir, artifacts_dir)
                osutils.copytree(cache_function_dir, artifacts_dir)
                function_build_results[function.name] = artifacts_dir

        return function_build_results

    def build_single_layer_definition(self, layer_definition):
        """
        Builds single layer definition with caching
        """
        code_dir = str(pathlib.Path(self._base_dir, layer_definition.codeuri).resolve())
        source_md5 = dir_checksum(code_dir)
        cache_function_dir = pathlib.Path(self._cache_dir, layer_definition.uuid)
        layer_build_result = {}

        if not cache_function_dir.exists() or layer_definition.source_md5 != source_md5:
            LOG.info("Cache is invalid, running build and copying resources to layer build definition of %s",
                     layer_definition.uuid)
            build_result = self._delegate_build_strategy.build_single_layer_definition(layer_definition)
            layer_build_result.update(build_result)

            if cache_function_dir.exists():
                shutil.rmtree(str(cache_function_dir))

            layer_definition.source_md5 = source_md5
            # Since all the build contents are same for a build definition, just copy any one of them into the cache
            for _, value in build_result.items():
                osutils.copytree(value, cache_function_dir)
                break
        else:
            LOG.info("Valid cache found, copying previously built resources from layer build definition of %s",
                     layer_definition.uuid)
            # artifacts directory will be created by the builder
            artifacts_dir = str(pathlib.Path(self._build_dir, layer_definition.layer.name))
            LOG.debug("Copying artifacts from %s to %s", cache_function_dir, artifacts_dir)
            osutils.copytree(cache_function_dir, artifacts_dir)
            layer_build_result[layer_definition.layer.name] = artifacts_dir

        return layer_build_result

    def _clean_redundant_cached(self):
        """
        clean the redundant cached folder
        """
        self._build_graph.clean_redundant_definitions_and_update(not self._is_building_specific_resource)
        uuids = {bd.uuid for bd in self._build_graph.get_function_build_definitions()}
        uuids.update({ld.uuid for ld in self._build_graph.get_layer_build_definitions()})
        for cache_dir in pathlib.Path(self._cache_dir).iterdir():
            if cache_dir.name not in uuids:
                shutil.rmtree(pathlib.Path(self._cache_dir, cache_dir.name))


class ParallelBuildStrategy(BuildStrategy):
    """
    Parallel implementation of Build Strategy
    This strategy runs each build in parallel.
    For actual build implementation it calls delegate implementation (could be one of the other Build Strategy)
    """

    def __init__(self, build_graph, delegate_build_strategy, async_context=AsyncContext()):
        super().__init__(build_graph)
        self._delegate_build_strategy = delegate_build_strategy
        self._async_context = async_context

    def build(self):
        """
        Runs all build and collects results from async context
        """
        result = {}
        with self, self._delegate_build_strategy:
            # ignore result
            super().build()
            # wait for other executions to complete

            async_results = self._async_context.run_async()
            for async_result in async_results:
                result.update(async_result)

        return result

    def build_single_function_definition(self, build_definition):
        """
        Passes single function build into async context, no actual result returned from this function
        """
        self._async_context.add_async_task(
            self._delegate_build_strategy.build_single_function_definition,
            build_definition
        )
        return {}

    def build_single_layer_definition(self, layer_definition):
        """
        Passes single layer build into async context, no actual result returned from this function
        """
        self._async_context.add_async_task(
            self._delegate_build_strategy.build_single_layer_definition,
            layer_definition
        )
        return {}
