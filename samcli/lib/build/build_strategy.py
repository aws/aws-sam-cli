"""
Keeps implementation of different build strategies
"""

import hashlib
import logging
import os.path
import pathlib
import shutil
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, cast

from samcli.commands._utils.experimental import ExperimentalFlag, is_experimental_enabled
from samcli.lib.build.build_graph import (
    DEFAULT_DEPENDENCIES_DIR,
    AbstractBuildDefinition,
    BuildGraph,
    FunctionBuildDefinition,
    LayerBuildDefinition,
)
from samcli.lib.build.dependency_hash_generator import DependencyHashGenerator
from samcli.lib.build.exceptions import MissingBuildMethodException
from samcli.lib.build.utils import warn_on_invalid_architecture
from samcli.lib.utils import osutils
from samcli.lib.utils.architecture import X86_64
from samcli.lib.utils.async_utils import AsyncContext
from samcli.lib.utils.hash import dir_checksum
from samcli.lib.utils.packagetype import IMAGE, ZIP

LOG = logging.getLogger(__name__)

# type definition which can be used in generic types for both FunctionBuildDefinition & LayerBuildDefinition
FunctionOrLayerBuildDefinition = TypeVar(
    "FunctionOrLayerBuildDefinition", FunctionBuildDefinition, LayerBuildDefinition
)


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

    for full_dir_path in base_dir_path.iterdir():
        if full_dir_path.name not in uuids and full_dir_path.is_dir():
            LOG.debug("Cleaning up redundant folder %s, which is not related to any function or layer", full_dir_path)
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
        build_function: Callable[
            [str, str, Optional[str], str, str, str, Optional[str], str, dict, dict, Optional[str], bool], str
        ],
        build_layer: Callable[[str, str, str, List[str], str, str, dict, Optional[str], bool, Optional[Dict]], str],
        cached: bool = False,
    ) -> None:
        super().__init__(build_graph)
        self._build_dir = build_dir
        self._build_function = build_function
        self._build_layer = build_layer
        self._cached = cached

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
            build_definition.get_resource_full_paths(),
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
            build_definition.imageuri,
            build_definition.packagetype,
            build_definition.runtime,  # type: ignore
            build_definition.architecture,
            build_definition.get_handler_name(),
            single_build_dir,
            build_definition.metadata,
            container_env_vars,
            build_definition.dependencies_dir if self._cached else None,
            build_definition.download_dependencies,
        )
        function_build_results[single_full_path] = result

        # copy results to other functions
        if build_definition.packagetype == ZIP:
            for function in build_definition.functions:
                if function.full_path != single_full_path:
                    # for zip function we need to refer over the result
                    # artifacts directory which have built as the action above
                    if is_experimental_enabled(ExperimentalFlag.BuildPerformance):
                        LOG.debug(
                            "Using previously build shared location %s for function %s", result, function.full_path
                        )
                        function_build_results[function.full_path] = result
                    else:
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

        if layer.build_method == "makefile":
            warn_on_invalid_architecture(layer_definition)

        # There are two cases where we'd like to warn the customer
        # 1. Compatible Architectures is only x86 (or not present) but Build Architecture is arm64
        # 2. Build Architecture is x86 (or not present) but Compatible Architectures is only arm64

        build_architecture = layer.build_architecture or X86_64
        compatible_architectures = layer.compatible_architectures or [X86_64]

        if build_architecture not in compatible_architectures:
            LOG.warning(
                "WARNING: Layer '%s' has BuildArchitecture %s, which is not listed in CompatibleArchitectures",
                layer.layer_id,
                build_architecture,
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
                layer_definition.dependencies_dir if self._cached else None,
                layer_definition.download_dependencies,
                layer.metadata,
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
                "Cache is invalid, running build and copying resources for following functions (%s)",
                build_definition.get_resource_full_paths(),
            )
            build_result = self._delegate_build_strategy.build_single_function_definition(build_definition)
            function_build_results.update(build_result)

            if cache_function_dir.exists():
                shutil.rmtree(str(cache_function_dir))

            build_definition.source_hash = source_hash
            # Since all the build contents are same for a build definition, just copy any one of them into the cache
            for _, value in build_result.items():
                osutils.copytree(value, str(cache_function_dir))
                break
        else:
            LOG.info(
                "Valid cache found, copying previously built resources for following functions (%s)",
                build_definition.get_resource_full_paths(),
            )
            if is_experimental_enabled(ExperimentalFlag.BuildPerformance):
                first_function_artifacts_dir: Optional[str] = None
                for function in build_definition.functions:
                    if not first_function_artifacts_dir:
                        # artifacts directory will be created by the builder
                        artifacts_dir = build_definition.get_build_dir(self._build_dir)
                        LOG.debug("Linking artifacts from %s to %s", cache_function_dir, artifacts_dir)
                        osutils.create_symlink_or_copy(str(cache_function_dir), artifacts_dir)
                        function_build_results[function.full_path] = artifacts_dir
                        first_function_artifacts_dir = artifacts_dir
                    else:
                        LOG.debug(
                            "Function (%s) build folder is updated to %s",
                            function.full_path,
                            first_function_artifacts_dir,
                        )
                        function_build_results[function.full_path] = first_function_artifacts_dir
            else:
                for function in build_definition.functions:
                    # artifacts directory will be created by the builder
                    artifacts_dir = function.get_build_dir(self._build_dir)
                    LOG.debug("Copying artifacts from %s to %s", cache_function_dir, artifacts_dir)
                    osutils.copytree(str(cache_function_dir), artifacts_dir)
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
                "Cache is invalid, running build and copying resources for following layers (%s)",
                layer_definition.get_resource_full_paths(),
            )
            build_result = self._delegate_build_strategy.build_single_layer_definition(layer_definition)
            layer_build_result.update(build_result)

            if cache_function_dir.exists():
                shutil.rmtree(str(cache_function_dir))

            layer_definition.source_hash = source_hash
            # Since all the build contents are same for a build definition, just copy any one of them into the cache
            for _, value in build_result.items():
                osutils.copytree(value, str(cache_function_dir))
                break
        else:
            LOG.info(
                "Valid cache found, copying previously built resources for following layers (%s)",
                layer_definition.get_resource_full_paths(),
            )
            # artifacts directory will be created by the builder
            artifacts_dir = layer_definition.layer.get_build_dir(self._build_dir)

            if is_experimental_enabled(ExperimentalFlag.BuildPerformance):
                LOG.debug("Linking artifacts folder from %s to %s", cache_function_dir, artifacts_dir)
                osutils.create_symlink_or_copy(str(cache_function_dir), artifacts_dir)
            else:
                LOG.debug("Copying artifacts from %s to %s", cache_function_dir, artifacts_dir)
                osutils.copytree(str(cache_function_dir), artifacts_dir)
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
    ) -> None:
        super().__init__(build_graph)
        self._delegate_build_strategy = delegate_build_strategy

    def build(self) -> Dict[str, str]:
        with self._delegate_build_strategy:
            return super().build()

    def _build_layers(self, build_graph: BuildGraph) -> Dict[str, str]:
        return self._run_builds_async(self.build_single_layer_definition, build_graph.get_layer_build_definitions())

    def _build_functions(self, build_graph: BuildGraph) -> Dict[str, str]:
        return self._run_builds_async(
            self.build_single_function_definition, build_graph.get_function_build_definitions()
        )

    @staticmethod
    def _run_builds_async(
        build_method: Callable[[FunctionOrLayerBuildDefinition], Dict[str, str]],
        build_definitions: Tuple[FunctionOrLayerBuildDefinition, ...],
    ) -> Dict[str, str]:
        """Builds given list of build definitions in async and return the result"""
        if not build_definitions:
            return dict()

        async_context = AsyncContext()
        for build_definition in build_definitions:
            async_context.add_async_task(build_method, build_definition)
        async_results = async_context.run_async()

        build_result: Dict[str, str] = dict()
        for async_result in async_results:
            build_result.update(async_result)
        return build_result

    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        return self._delegate_build_strategy.build_single_layer_definition(layer_definition)

    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        return self._delegate_build_strategy.build_single_function_definition(build_definition)


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
                    "Manifest file is changed (new hash: %s) or dependency folder (%s) is missing for (%s), "
                    "downloading dependencies and copying/building source",
                    manifest_hash,
                    build_definition.dependencies_dir,
                    build_definition.get_resource_full_paths(),
                )
            else:
                LOG.info(
                    "Manifest is not changed for (%s), running incremental build",
                    build_definition.get_resource_full_paths(),
                )

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
        use_container: bool,
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
        self._use_container = use_container

    def build(self) -> Dict[str, str]:
        result = {}
        with self._cached_build_strategy, self._incremental_build_strategy:
            result.update(super().build())
        return result

    def build_single_function_definition(self, build_definition: FunctionBuildDefinition) -> Dict[str, str]:
        if self._is_incremental_build_supported(build_definition.runtime):
            LOG.debug(
                "Running incremental build for runtime %s for following resources (%s)",
                build_definition.runtime,
                build_definition.get_resource_full_paths(),
            )
            return self._incremental_build_strategy.build_single_function_definition(build_definition)

        LOG.debug(
            "Running incremental build for runtime %s for following resources (%s)",
            build_definition.runtime,
            build_definition.get_resource_full_paths(),
        )
        return self._cached_build_strategy.build_single_function_definition(build_definition)

    def build_single_layer_definition(self, layer_definition: LayerBuildDefinition) -> Dict[str, str]:
        if self._is_incremental_build_supported(layer_definition.build_method):
            LOG.debug(
                "Running incremental build for runtime %s for following resources (%s)",
                layer_definition.build_method,
                layer_definition.get_resource_full_paths(),
            )
            return self._incremental_build_strategy.build_single_layer_definition(layer_definition)

        LOG.debug(
            "Running cached build for runtime %s for following resources (%s)",
            layer_definition.build_method,
            layer_definition.get_resource_full_paths,
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

    def _is_incremental_build_supported(self, runtime: Optional[str]) -> bool:
        # incremental build doesn't support in container build
        if self._use_container:
            return False

        if not runtime:
            return False

        for supported_runtime_prefix in CachedOrIncrementalBuildStrategyWrapper.SUPPORTED_RUNTIME_PREFIXES:
            if runtime.startswith(supported_runtime_prefix):
                return True

        return False
