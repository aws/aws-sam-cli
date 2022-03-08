"""
Keeps implementation of different build strategies
"""
import hashlib
import logging
import os.path
import pathlib
import shutil
from abc import abstractmethod, ABC
from copy import deepcopy
from typing import Callable, Dict, List, Any, Optional, cast, Set

from samcli.commands._utils.experimental import is_experimental_enabled, ExperimentalFlag
from samcli.lib.utils import osutils
from samcli.lib.utils.async_utils import AsyncContext
from samcli.lib.utils.hash import dir_checksum
from samcli.lib.utils.packagetype import ZIP, IMAGE
from samcli.lib.build.dependency_hash_generator import DependencyHashGenerator
from samcli.lib.build.build_graph import (
    BuildGraph,
    FunctionBuildDefinition,
    LayerBuildDefinition,
    AbstractBuildDefinition,
    DEFAULT_DEPENDENCIES_DIR,
)
from samcli.lib.build.exceptions import MissingBuildMethodException


LOG = logging.getLogger(__name__)


def clean_redundant_folders(base_dir: str, uuids: Set[str]) -> None:
    """
    Compares existing folders inside base_dir and removes the ones which is not in the uuids set.

    Parameters
    ----------
    base_dir : str
        Base directory that it will be operating
    uuids : Set[str]
        Expected folder names. If any folder name in the base_dir is not present in this Set, it will be deleted.
    """
    base_dir_path = pathlib.Path(base_dir)

    if not base_dir_path.exists():
        return

    for full_dir_path in pathlib.Path(base_dir).iterdir():
        if full_dir_path.name not in uuids:
            shutil.rmtree(pathlib.Path(base_dir, full_dir_path.name))


class BuildStrategy(ABC):
    """
    Base class for BuildStrategy
    Keeps basic implementation of build, build_functions and build_layers
    """

    def __init__(self, build_graph: BuildGraph) -> None:
        self._build_graph = build_graph

    def __enter__(self) -> None:
        pass

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    def build(self) -> Dict[str, str]:
        """
        Builds all functions and layers in the given build graph
        """
        result = {}
        with self:
            result.update(self._build_layers(self._build_graph))
            result.update(self._build_functions(self._build_graph))

        return result

    def _build_functions(self, build_graph: BuildGraph) -> Dict[str, str]:
        """
        Iterates through build graph and runs each unique build and copies outcome to the corresponding function folder
        """
        function_build_results = {}
        for build_definition in build_graph.get_function_build_definitions():
            function_build_results.update(self.build_single_function_definition(build_definition))

        return function_build_results

    @abstractmethod
    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        """
        Builds single function definition and returns dictionary which contains function name as key,
        build location as value
        """

    def _build_layers(self, build_graph: BuildGraph) -> Dict[str, str]:
        """
        Iterates through build graph and runs each unique build and copies outcome to the corresponding layer folder
        """
        layer_build_results = {}
        for layer_definition in build_graph.get_layer_build_definitions():
            layer_build_results.update(self.build_single_layer_definition(layer_definition))

        return layer_build_results

    @abstractmethod
    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        """
        Builds single layer definition and returns dictionary which contains layer name as key,
        build location as value
        """


class DefaultBuildStrategy(BuildStrategy):
    """
    Default build strategy, loops over given build graph for each function and layer, and builds each of them one by one
    """

    def __init__(
        self,
        build_graph: BuildGraph,
        build_dir: str,
        build_function: Callable[[str, str, str, str, str, Optional[str], str, dict, dict, Optional[str], bool], str],
        build_layer: Callable[[str, str, str, List[str], str, str, dict, Optional[str], bool], str],
    ) -> None:
        super().__init__(build_graph)
        self._build_dir = build_dir
        self._build_function = build_function
        self._build_layer = build_layer

    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        """
        Build the unique definition and then copy the artifact to the corresponding function folder
        """
        function_build_results = {}
        LOG.info(
            "Building codeuri: %s runtime: %s metadata: %s architecture: %s functions: %s",
            build_definition.codeuri,
            build_definition.runtime,
            build_definition.metadata,
            build_definition.architecture,
            [function.full_path for function in build_definition.functions],
        )

        # build into one of the functions from this build definition
        single_full_path = build_definition.get_full_path()
        single_build_dir = build_definition.get_build_dir(self._build_dir)

        LOG.debug("Building to following folder %s", single_build_dir)

        # we should create a copy and pass it down, otherwise additional env vars like LAMBDA_BUILDERS_LOG_LEVEL
        # will make cache invalid all the time
        container_env_vars = deepcopy(build_definition.env_vars)

        # when a function is passed here, it is ZIP function, codeuri and runtime are not None
        result = self._build_function(
            build_definition.get_function_name(),
            build_definition.codeuri,  # type: ignore
            build_definition.packagetype,
            build_definition.runtime,  # type: ignore
            build_definition.architecture,
            build_definition.get_handler_name(),
            single_build_dir,
            build_definition.metadata,
            container_env_vars,
            build_definition.dependencies_dir if is_experimental_enabled(ExperimentalFlag.Accelerate) else None,
            build_definition.download_dependencies,
        )
        function_build_results[single_full_path] = result

        # copy results to other functions
        if build_definition.packagetype == ZIP:
            for function in build_definition.functions:
                if function.full_path != single_full_path:
                    # for zip function we need to copy over the artifacts
                    # artifacts directory will be created by the builder
                    artifacts_dir = function.get_build_dir(self._build_dir)
                    LOG.debug("Copying artifacts from %s to %s", single_build_dir, artifacts_dir)
                    osutils.copytree(single_build_dir, artifacts_dir)
                    function_build_results[function.full_path] = artifacts_dir
        elif build_definition.packagetype == IMAGE:
            for function in build_definition.functions:
                if function.full_path != single_full_path:
                    # for image function, we just need to copy the image tag
                    function_build_results[function.full_path] = result

        return function_build_results

    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        """
        Build the unique definition and then copy the artifact to the corresponding layer folder
        """
        layer = layer_definition.layer
        LOG.info("Building layer '%s'", layer.full_path)
        if layer.build_method is None:
            raise MissingBuildMethodException(
                f"Layer {layer.full_path} cannot be build without BuildMethod. "
                f"Please provide BuildMethod in Metadata."
            )

        single_build_dir = layer.get_build_dir(self._build_dir)
        # when a layer is passed here, it is ZIP function, codeuri and runtime are not None
        # codeuri and compatible_runtimes are not None
        return {
            layer.full_path: self._build_layer(
                layer.name,
                layer.codeuri,  # type: ignore
                layer.build_method,
                layer.compatible_runtimes,  # type: ignore
                layer.build_architecture,
                single_build_dir,
                layer_definition.env_vars,
                layer_definition.dependencies_dir if is_experimental_enabled(ExperimentalFlag.Accelerate) else None,
                layer_definition.download_dependencies,
            )
        }


class CachedBuildStrategy(BuildStrategy):
    """
    Cached implementation of Build Strategy
    For each function and layer, it first checks if there is a valid cache, and if there is, it copies from previous
    build. If caching is invalid, it builds function or layer from scratch and updates cache folder and hash of the
    function or layer.
    For actual building, it uses delegate implementation
    """

    def __init__(
        self,
        build_graph: BuildGraph,
        delegate_build_strategy: BuildStrategy,
        base_dir: str,
        build_dir: str,
        cache_dir: str,
    ) -> None:
        super().__init__(build_graph)
        self._delegate_build_strategy = delegate_build_strategy
        self._base_dir = base_dir
        self._build_dir = build_dir
        self._cache_dir = cache_dir

    def build(self) -> Dict[str, str]:
        result = {}
        with self._delegate_build_strategy:
            result.update(super().build())
        return result

    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        """
        Builds single function definition with caching
        """
        if build_definition.packagetype == IMAGE:
            return self._delegate_build_strategy.build_single_function_definition(build_definition)

        code_dir = str(pathlib.Path(self._base_dir, cast(str, build_definition.codeuri)).resolve())
        source_hash = dir_checksum(code_dir, ignore_list=[".aws-sam"], hash_generator=hashlib.sha256())
        cache_function_dir = pathlib.Path(self._cache_dir, build_definition.uuid)
        function_build_results = {}

        if not cache_function_dir.exists() or build_definition.source_hash != source_hash:
            LOG.info(
                "Cache is invalid, running build and copying resources to function build definition of %s",
                build_definition.uuid,
            )
            build_result = self._delegate_build_strategy.build_single_function_definition(build_definition)
            function_build_results.update(build_result)

            if cache_function_dir.exists():
                shutil.rmtree(str(cache_function_dir))

            build_definition.source_hash = source_hash
            # Since all the build contents are same for a build definition, just copy any one of them into the cache
            for _, value in build_result.items():
                osutils.copytree(value, cache_function_dir)
                break
        else:
            LOG.info(
                "Valid cache found, copying previously built resources from function build definition of %s",
                build_definition.uuid,
            )
            for function in build_definition.functions:
                # artifacts directory will be created by the builder
                artifacts_dir = function.get_build_dir(self._build_dir)
                LOG.debug("Copying artifacts from %s to %s", cache_function_dir, artifacts_dir)
                osutils.copytree(cache_function_dir, artifacts_dir)
                function_build_results[function.full_path] = artifacts_dir

        return function_build_results

    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        """
        Builds single layer definition with caching
        """
        code_dir = str(pathlib.Path(self._base_dir, cast(str, layer_definition.codeuri)).resolve())
        source_hash = dir_checksum(code_dir, ignore_list=[".aws-sam"], hash_generator=hashlib.sha256())
        cache_function_dir = pathlib.Path(self._cache_dir, layer_definition.uuid)
        layer_build_result = {}

        if not cache_function_dir.exists() or layer_definition.source_hash != source_hash:
            LOG.info(
                "Cache is invalid, running build and copying resources to layer build definition of %s",
                layer_definition.uuid,
            )
            build_result = self._delegate_build_strategy.build_single_layer_definition(layer_definition)
            layer_build_result.update(build_result)

            if cache_function_dir.exists():
                shutil.rmtree(str(cache_function_dir))

            layer_definition.source_hash = source_hash
            # Since all the build contents are same for a build definition, just copy any one of them into the cache
            for _, value in build_result.items():
                osutils.copytree(value, cache_function_dir)
                break
        else:
            LOG.info(
                "Valid cache found, copying previously built resources from layer build definition of %s",
                layer_definition.uuid,
            )
            # artifacts directory will be created by the builder
            artifacts_dir = str(pathlib.Path(self._build_dir, layer_definition.layer.full_path))
            LOG.debug("Copying artifacts from %s to %s", cache_function_dir, artifacts_dir)
            osutils.copytree(cache_function_dir, artifacts_dir)
            layer_build_result[layer_definition.layer.full_path] = artifacts_dir

        return layer_build_result

    def _clean_redundant_cached(self) -> None:
        """
        clean the redundant cached folder
        """
        uuids = {bd.uuid for bd in self._build_graph.get_function_build_definitions()}
        uuids.update({ld.uuid for ld in self._build_graph.get_layer_build_definitions()})
        clean_redundant_folders(self._cache_dir, uuids)


class ParallelBuildStrategy(BuildStrategy):
    """
    Parallel implementation of Build Strategy
    This strategy runs each build in parallel.
    For actual build implementation it calls delegate implementation (could be one of the other Build Strategy)
    """

    def __init__(
        self,
        build_graph: BuildGraph,
        delegate_build_strategy: BuildStrategy,
        async_context: Optional[AsyncContext] = None,
    ) -> None:
        super().__init__(build_graph)
        self._delegate_build_strategy = delegate_build_strategy
        self._async_context = async_context if async_context else AsyncContext()

    def build(self) -> Dict[str, str]:
        """
        Runs all build and collects results from async context
        """
        result = {}
        with self._delegate_build_strategy:
            # ignore result
            super().build()
            # wait for other executions to complete

            async_results = self._async_context.run_async()
            for async_result in async_results:
                result.update(async_result)

        return result

    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        """
        Passes single function build into async context, no actual result returned from this function
        """
        self._async_context.add_async_task(
            self._delegate_build_strategy.build_single_function_definition, build_definition
        )
        return {}

    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        """
        Passes single layer build into async context, no actual result returned from this function
        """
        self._async_context.add_async_task(
            self._delegate_build_strategy.build_single_layer_definition, layer_definition
        )
        return {}


class IncrementalBuildStrategy(BuildStrategy):
    """
    Incremental build is supported for certain runtimes in aws-lambda-builders, with dependencies_dir (str)
    and download_dependencies (bool) options.

    This build strategy sets whether we need to download dependencies again (download_dependencies option) by comparing
    the hash of the manifest file of the given runtime as well as the dependencies directory location
    (dependencies_dir option).
    """

    def __init__(
        self,
        build_graph: BuildGraph,
        delegate_build_strategy: BuildStrategy,
        base_dir: str,
        manifest_path_override: Optional[str],
    ):
        super().__init__(build_graph)
        self._delegate_build_strategy = delegate_build_strategy
        self._base_dir = base_dir
        self._manifest_path_override = manifest_path_override

    def build(self) -> Dict[str, str]:
        result = {}
        with self, self._delegate_build_strategy:
            result.update(super().build())
        return result

    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        self._check_whether_manifest_is_changed(build_definition, build_definition.codeuri, build_definition.runtime)
        return self._delegate_build_strategy.build_single_function_definition(build_definition)

    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        self._check_whether_manifest_is_changed(
            layer_definition, layer_definition.codeuri, layer_definition.build_method
        )
        return self._delegate_build_strategy.build_single_layer_definition(layer_definition)

    def _check_whether_manifest_is_changed(
        self,
        build_definition: AbstractBuildDefinition,
        codeuri: Optional[str],
        runtime: Optional[str],
    ) -> None:
        """
        Checks whether the manifest file have been changed by comparing its hash with previously stored one and updates
        download_dependencies property of build definition to True, if it is changed
        """
        manifest_hash = DependencyHashGenerator(
            cast(str, codeuri), self._base_dir, cast(str, runtime), self._manifest_path_override
        ).hash

        is_manifest_changed = True
        is_dependencies_dir_missing = True
        if manifest_hash:
            is_manifest_changed = manifest_hash != build_definition.manifest_hash
            is_dependencies_dir_missing = not os.path.exists(build_definition.dependencies_dir)
            if is_manifest_changed or is_dependencies_dir_missing:
                build_definition.manifest_hash = manifest_hash
                LOG.info(
                    "Manifest file is changed (new hash: %s) or dependency folder (%s) is missing for %s, "
                    "downloading dependencies and copying/building source",
                    manifest_hash,
                    build_definition.dependencies_dir,
                    build_definition.uuid,
                )
            else:
                LOG.info("Manifest is not changed for %s, running incremental build", build_definition.uuid)

        build_definition.download_dependencies = is_manifest_changed or is_dependencies_dir_missing

    def _clean_redundant_dependencies(self) -> None:
        """
        Update build definitions with possible new manifest hash information and clean the redundant dependencies folder
        """
        uuids = {bd.uuid for bd in self._build_graph.get_function_build_definitions()}
        uuids.update({ld.uuid for ld in self._build_graph.get_layer_build_definitions()})
        clean_redundant_folders(DEFAULT_DEPENDENCIES_DIR, uuids)


class CachedOrIncrementalBuildStrategyWrapper(BuildStrategy):
    """
    A wrapper class which holds instance of CachedBuildStrategy and IncrementalBuildStrategy
    to select one of them during function or layer build, depending on the runtime that they are using
    """

    SUPPORTED_RUNTIME_PREFIXES: Set[str] = {
        "python",
        "ruby",
        "nodejs",
    }

    def __init__(
        self,
        build_graph: BuildGraph,
        delegate_build_strategy: BuildStrategy,
        base_dir: str,
        build_dir: str,
        cache_dir: str,
        manifest_path_override: Optional[str],
        is_building_specific_resource: bool,
    ):
        super().__init__(build_graph)
        self._incremental_build_strategy = IncrementalBuildStrategy(
            build_graph,
            delegate_build_strategy,
            base_dir,
            manifest_path_override,
        )
        self._cached_build_strategy = CachedBuildStrategy(
            build_graph,
            delegate_build_strategy,
            base_dir,
            build_dir,
            cache_dir,
        )
        self._is_building_specific_resource = is_building_specific_resource

    def build(self) -> Dict[str, str]:
        result = {}
        with self._cached_build_strategy, self._incremental_build_strategy:
            result.update(super().build())
        return result

    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        if self._is_incremental_build_supported(build_definition.runtime):
            LOG.debug(
                "Running incremental build for runtime %s for build definition %s",
                build_definition.runtime,
                build_definition.uuid,
            )
            return self._incremental_build_strategy.build_single_function_definition(build_definition)

        LOG.debug(
            "Running incremental build for runtime %s for build definition %s",
            build_definition.runtime,
            build_definition.uuid,
        )
        return self._cached_build_strategy.build_single_function_definition(build_definition)

    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        if self._is_incremental_build_supported(layer_definition.build_method):
            LOG.debug(
                "Running incremental build for runtime %s for build definition %s",
                layer_definition.build_method,
                layer_definition.uuid,
            )
            return self._incremental_build_strategy.build_single_layer_definition(layer_definition)

        LOG.debug(
            "Running cached build for runtime %s for build definition %s",
            layer_definition.build_method,
            layer_definition.uuid,
        )
        return self._cached_build_strategy.build_single_layer_definition(layer_definition)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        After build is complete, this method cleans up redundant folders in cached directory as well as in dependencies
        directory. This also updates hashes of the functions and layers, if only single function or layer is been built.

        If SAM CLI switched to use only IncrementalBuildStrategy, contents of this method should be moved inside
        IncrementalBuildStrategy so that it will still continue to clean-up redundant folders.
        """
        if self._is_building_specific_resource:
            self._build_graph.update_definition_hash()
        else:
            self._build_graph.clean_redundant_definitions_and_update(not self._is_building_specific_resource)
            self._cached_build_strategy._clean_redundant_cached()
            self._incremental_build_strategy._clean_redundant_dependencies()

    @staticmethod
    def _is_incremental_build_supported(runtime: Optional[str]) -> bool:
        if not runtime or not is_experimental_enabled(ExperimentalFlag.Accelerate):
            return False

        for supported_runtime_prefix in CachedOrIncrementalBuildStrategyWrapper.SUPPORTED_RUNTIME_PREFIXES:
            if runtime.startswith(supported_runtime_prefix):
                return True

        return False
