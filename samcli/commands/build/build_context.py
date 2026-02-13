"""
Context object used by build command
"""

import logging
import os
import pathlib
import shutil
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import click

from samcli.commands._utils.constants import DEFAULT_BUILD_DIR
from samcli.commands._utils.experimental import ExperimentalFlag, prompt_experimental
from samcli.commands._utils.template import (
    FOREACH_REQUIRED_ELEMENTS,
    get_template_data,
    move_template,
)
from samcli.commands.build.exceptions import InvalidBuildDirException, MissingBuildMethodException
from samcli.commands.build.utils import MountMode, prompt_user_to_enable_mount_with_write_if_needed
from samcli.commands.exceptions import UserException
from samcli.lib.bootstrap.nested_stack.nested_stack_manager import NESTED_STACK_NAME, NestedStackManager
from samcli.lib.build.app_builder import (
    ApplicationBuilder,
    ApplicationBuildResult,
    BuildError,
    UnsupportedBuilderLibraryVersionError,
)
from samcli.lib.build.build_graph import DEFAULT_DEPENDENCIES_DIR
from samcli.lib.build.bundler import EsbuildBundlerManager
from samcli.lib.build.exceptions import (
    BuildInsideContainerError,
    InvalidBuildGraphException,
)
from samcli.lib.build.workflow_config import UnsupportedRuntimeException
from samcli.lib.cfn_language_extensions.sam_integration import (
    contains_loop_variable,
    sanitize_resource_key_for_mapping,
    substitute_loop_variable,
)
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.providers.provider import LayerVersion, ResourcesToBuildCollector, Stack
from samcli.lib.providers.sam_api_provider import SamApiProvider
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_layer_provider import SamLayerProvider
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.telemetry.event import EventName, EventTracker, UsedFeature
from samcli.lib.utils.osutils import BUILD_DIR_PERMISSIONS
from samcli.local.docker.manager import ContainerManager
from samcli.local.lambdafn.exceptions import (
    FunctionNotFound,
    ResourceNotFound,
)

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
        hook_name: Optional[str] = None,
        build_in_source: Optional[bool] = None,
        mount_with: str = MountMode.READ.value,
        mount_symlinks: Optional[bool] = False,
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
        hook_name: Optional[str]
            Name of the hook package
        build_in_source: Optional[bool]
            Set to True to build in the source directory.
        mount_with:
            Mount mode of source code directory when building inside container, READ ONLY by default
        mount_symlinks Optional[bool]:
            Indicates if symlinks should be mounted inside the container
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
        self._hook_name = hook_name
        self._build_in_source = build_in_source
        self._build_result: Optional[ApplicationBuildResult] = None
        self._mount_with = MountMode(mount_with)
        self._mount_symlinks = mount_symlinks

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

    def run(self) -> None:
        """Runs the building process by creating an ApplicationBuilder."""
        if self._is_sam_template():
            SamApiProvider.check_implicit_api_resource_ids(self.stacks)

        self._stacks = self._handle_build_pre_processing()

        caught_exception: Optional[Exception] = None

        try:
            # boolean value indicates if mount with write or not, defaults to READ ONLY
            mount_with_write = False
            if self._use_container:
                if self._mount_with == MountMode.WRITE:
                    mount_with_write = True
                else:
                    # if self._mount_with is NOT WRITE
                    # check the need of mounting with write permissions and prompt user to enable it if needed
                    mount_with_write = prompt_user_to_enable_mount_with_write_if_needed(
                        self.get_resources_to_build(),
                        self.base_dir,
                    )

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
                build_in_source=self._build_in_source,
                mount_with_write=mount_with_write,
                mount_symlinks=self._mount_symlinks,
            )

            self._check_exclude_warning()
            self._check_build_method_experimental_flag()

            for f in self.get_resources_to_build().functions:
                EventTracker.track_event(EventName.BUILD_FUNCTION_RUNTIME.value, f.runtime)

            self._build_result = builder.build()

            self._handle_build_post_processing(builder, self._build_result)

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
                msg = self._gen_success_msg(
                    build_dir_in_success_message,
                    output_template_path_in_success_message,
                    os.path.abspath(self.build_dir) == os.path.abspath(DEFAULT_BUILD_DIR),
                )

                click.secho(msg, fg="yellow")
        except FunctionNotFound as function_not_found_ex:
            caught_exception = function_not_found_ex

            raise UserException(
                str(function_not_found_ex), wrapped_from=function_not_found_ex.__class__.__name__
            ) from function_not_found_ex
        except (
            UnsupportedRuntimeException,
            BuildError,
            BuildInsideContainerError,
            UnsupportedBuilderLibraryVersionError,
            InvalidBuildGraphException,
            ResourceNotFound,
        ) as ex:
            caught_exception = ex

            click.secho("\nBuild Failed", fg="red")

            # Some Exceptions have a deeper wrapped exception that needs to be surfaced
            # from deeper than just one level down.
            deep_wrap = getattr(ex, "wrapped_from", None)
            wrapped_from = deep_wrap if deep_wrap else ex.__class__.__name__
            raise UserException(str(ex), wrapped_from=wrapped_from) from ex
        finally:
            if self.build_in_source:
                exception_name = type(caught_exception).__name__ if caught_exception else None
                EventTracker.track_event(
                    EventName.USED_FEATURE.value, UsedFeature.BUILD_IN_SOURCE.value, exception_name
                )

    def _is_sam_template(self) -> bool:
        """Check if a given template is a SAM template"""
        template_dict = get_template_data(self._template_file)
        template_transforms = template_dict.get("Transform", [])
        if not isinstance(template_transforms, list):
            template_transforms = [template_transforms]
        for template_transform in template_transforms:
            if isinstance(template_transform, str) and template_transform.startswith("AWS::Serverless"):
                return True
        return False

    def _handle_build_pre_processing(self) -> List[Stack]:
        """
        Pre-modify the stacks as required before invoking the build
        :return: List of modified stacks
        """
        stacks = []
        if any(EsbuildBundlerManager(stack).esbuild_configured() for stack in self.stacks):
            # esbuild is configured in one of the stacks, will check and update stack metadata accordingly
            for stack in self.stacks:
                stacks.append(EsbuildBundlerManager(stack).set_sourcemap_metadata_from_env())
            self.function_provider.update(stacks, self._use_raw_codeuri, locate_layer_nested=self._locate_layer_nested)
        return stacks if stacks else self.stacks

    def _handle_build_post_processing(self, builder: ApplicationBuilder, build_result: ApplicationBuildResult) -> None:
        """
        Add any template modifications necessary before moving the template to build directory
        :param stack: Stack resources
        :param template: Current template file
        :param build_result: Result of the application build
        :return: Modified template dict
        """
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

            stack_name = self._stack_name if self._stack_name else ""
            if self._create_auto_dependency_layer:
                LOG.debug("Auto creating dependency layer for each function resource into a nested stack")
                nested_stack_manager = NestedStackManager(
                    stack, stack_name, self.build_dir, modified_template, build_result
                )
                modified_template = nested_stack_manager.generate_auto_dependency_layer_stack()

            esbuild_manager = EsbuildBundlerManager(stack=stack, template=modified_template, build_dir=self.build_dir)
            if esbuild_manager.esbuild_configured():
                modified_template = esbuild_manager.handle_template_post_processing()

            # Determine which template to write to disk
            # If the stack has an original template (with Fn::ForEach intact), use it
            # Otherwise, use the modified (expanded) template
            template_to_write = self._get_template_for_output(stack, modified_template, artifacts)

            move_template(stack.location, output_template_path, template_to_write)

    def _get_template_for_output(self, stack: Stack, modified_template: Dict, artifacts: Dict[str, str]) -> Dict:
        """
        Get the template to write to the build output directory.

        For templates with language extensions (Fn::ForEach), we preserve the original
        template structure and update artifact paths within the Fn::ForEach constructs.
        This ensures CloudFormation can process the AWS::LanguageExtensions transform
        server-side.

        Parameters
        ----------
        stack : Stack
            The stack being processed
        modified_template : Dict
            The expanded template with updated artifact paths
        artifacts : Dict[str, str]
            Map of resource full paths to their built artifact locations

        Returns
        -------
        Dict
            The template to write to disk
        """
        import copy

        # If no original template, use the modified (expanded) template
        # Check if original_template_dict exists and is a dict (not a Mock or other type)
        original_template_dict = getattr(stack, "original_template_dict", None)
        if not isinstance(original_template_dict, dict):
            return modified_template

        # Use the original template (with Fn::ForEach intact)
        # We need to update artifact paths in the Fn::ForEach constructs
        original_template = copy.deepcopy(original_template_dict)

        # Update artifact paths in the original template
        self._update_original_template_paths(original_template, modified_template, stack)

        # Propagate the auto dependency layer nested stack resource from the expanded template
        # into the original template. This resource is a regular AWS::CloudFormation::Stack type
        # added by NestedStackManager and does not conflict with Fn::ForEach constructs.
        modified_resources = modified_template.get("Resources", {})
        if NESTED_STACK_NAME in modified_resources:
            original_template.setdefault("Resources", {})[NESTED_STACK_NAME] = modified_resources[NESTED_STACK_NAME]

        return original_template

    def _update_original_template_paths(self, original_template: Dict, modified_template: Dict, stack: Stack) -> None:
        """
        Update artifact paths in the original template based on the modified template.

        This method handles Fn::ForEach constructs by finding the corresponding
        artifact paths from the expanded template and updating the original template.
        For dynamic artifact properties, it generates Mappings sections.

        Parameters
        ----------
        original_template : Dict
            The original template with Fn::ForEach constructs (will be modified in place)
        modified_template : Dict
            The expanded template with updated artifact paths
        stack : Stack
            The stack being processed
        """
        # Get the resources section from both templates
        original_resources = original_template.get("Resources", {})
        modified_resources = modified_template.get("Resources", {})

        # Collect all generated Mappings from dynamic artifact properties
        all_generated_mappings: Dict[str, Dict[str, Dict[str, str]]] = {}

        # Process each resource in the original template
        for resource_key, resource_value in original_resources.items():
            # Check if this is a Fn::ForEach construct
            if resource_key.startswith("Fn::ForEach::"):
                generated_mappings = self._update_foreach_artifact_paths(
                    resource_key,
                    resource_value,
                    modified_resources,
                    template=original_template,
                    parameter_values=stack.parameters,
                )
                all_generated_mappings.update(generated_mappings)
            elif isinstance(resource_value, dict) and resource_key in modified_resources:
                # Regular resource - copy updated paths from modified template
                modified_resource = modified_resources.get(resource_key, {})
                self._copy_artifact_paths(resource_value, modified_resource)

        # Merge generated Mappings into the template
        if all_generated_mappings:
            if "Mappings" not in original_template:
                original_template["Mappings"] = {}
            original_template["Mappings"].update(all_generated_mappings)

    def _update_foreach_artifact_paths(
        self,
        foreach_key: str,
        foreach_value: list,
        modified_resources: Dict,
        outer_context: Optional[List[Tuple[str, List[str]]]] = None,
        template: Optional[Dict] = None,
        parameter_values: Optional[Dict] = None,
        parent_nesting_path: str = "",
    ) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Update artifact paths in a Fn::ForEach construct.

        Recurses into nested Fn::ForEach blocks, passing outer loop context so that
        expanded resource names can be fully resolved.

        Parameters
        ----------
        foreach_key : str
            The Fn::ForEach key (e.g., "Fn::ForEach::Functions")
        foreach_value : list
            The Fn::ForEach value [loop_var, collection, body]
        modified_resources : Dict
            The expanded resources with updated artifact paths
        outer_context : list of tuples, optional
            Enclosing loop variables and their collections for nested ForEach.
        template : dict, optional
            The full original template (for resolving parameter-ref collections)
        parameter_values : dict, optional
            Parameter values (for resolving parameter-ref collections)
        parent_nesting_path : str
            Accumulated nesting path from parent ForEach loops (e.g., "Envs" when
            nested under Fn::ForEach::Envs).

        Returns
        -------
        Dict[str, Dict[str, Dict[str, str]]]
            Generated Mappings section for dynamic artifact properties (empty dict if none)
        """
        from samcli.lib.cfn_language_extensions.models import PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES
        from samcli.lib.cfn_language_extensions.sam_integration import resolve_collection

        generated_mappings: Dict[str, Dict[str, Dict[str, str]]] = {}

        if outer_context is None:
            outer_context = []

        if not isinstance(foreach_value, list) or len(foreach_value) < FOREACH_REQUIRED_ELEMENTS:
            return generated_mappings

        loop_variable = foreach_value[0]
        collection = foreach_value[1]
        body = foreach_value[2]

        if not isinstance(loop_variable, str) or not isinstance(body, dict):
            return generated_mappings

        collection_values = resolve_collection(collection, template or {}, parameter_values)

        loop_name = foreach_key.replace("Fn::ForEach::", "")
        nesting_path = parent_nesting_path + loop_name
        current_outer_context = outer_context + [(loop_variable, collection_values)]

        dynamic_props_count = self._count_dynamic_properties(body, loop_variable, collection_values)

        for resource_template_key, resource_template in body.items():
            if isinstance(resource_template_key, str) and resource_template_key.startswith("Fn::ForEach::"):
                nested_mappings = self._update_foreach_artifact_paths(
                    resource_template_key,
                    resource_template,
                    modified_resources,
                    outer_context=current_outer_context,
                    template=template,
                    parameter_values=parameter_values,
                    parent_nesting_path=nesting_path,
                )
                generated_mappings.update(nested_mappings)
                continue

            if not isinstance(resource_template, dict):
                continue

            resource_type = resource_template.get("Type", "")
            properties = resource_template.get("Properties", {})
            if not isinstance(properties, dict):
                continue

            for prop_name in PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.get(resource_type, []):
                prop_value = properties.get(prop_name)
                if prop_value is None:
                    continue

                if contains_loop_variable(prop_value, loop_variable) and collection_values:
                    # Determine which outer loop variables the property references
                    referenced_outer_vars = []
                    if outer_context:
                        referenced_outer_vars = [
                            (ovar, ocoll) for ovar, ocoll in outer_context if contains_loop_variable(prop_value, ovar)
                        ]

                    mapping_entries = self._collect_dynamic_mapping_entries(
                        resource_template_key,
                        prop_name,
                        loop_variable,
                        collection_values,
                        modified_resources,
                        outer_context,
                        referenced_outer_vars=referenced_outer_vars,
                    )
                    if mapping_entries:
                        mapping_name = f"SAM{prop_name}{nesting_path}"
                        if dynamic_props_count.get(prop_name, 0) > 1:
                            suffix = sanitize_resource_key_for_mapping(resource_template_key)
                            mapping_name = f"{mapping_name}{suffix}"
                        generated_mappings[mapping_name] = mapping_entries

                        lookup_key: Any
                        if referenced_outer_vars:
                            # Compound key: join outer + inner variable refs with "-"
                            ref_parts = [{"Ref": ovar} for ovar, _ in referenced_outer_vars]
                            ref_parts.append({"Ref": loop_variable})
                            lookup_key = {"Fn::Join": ["-", ref_parts]}
                        else:
                            lookup_key = {"Ref": loop_variable}

                        properties[prop_name] = {"Fn::FindInMap": [mapping_name, lookup_key, prop_name]}
                else:
                    expanded_key = self._build_expanded_key(
                        resource_template_key,
                        loop_variable,
                        collection_values,
                        outer_context,
                    )
                    if expanded_key:
                        artifact_value = self._get_artifact_value(modified_resources, expanded_key, prop_name)
                        if artifact_value is not None:
                            properties[prop_name] = artifact_value

            # Propagate auto dependency layer references from expanded functions
            # to the ForEach body. Each expanded function may have Layers entries
            # added by NestedStackManager referencing the nested stack outputs.
            # We use a Mappings-based approach (same as dynamic artifact paths)
            # to map each collection value to its layer output key.
            layer_mappings = self._collect_foreach_layer_mappings(
                resource_template_key,
                loop_variable,
                collection_values,
                modified_resources,
                outer_context,
            )
            if layer_mappings:
                layer_mapping_name = f"SAMLayers{nesting_path}"
                generated_mappings[layer_mapping_name] = layer_mappings

                layer_lookup_key: Any
                if outer_context:
                    referenced_outer = [
                        (ovar, ocoll)
                        for ovar, ocoll in outer_context
                        if contains_loop_variable(resource_template_key, ovar)
                    ]
                    if referenced_outer:
                        ref_parts = [{"Ref": ovar} for ovar, _ in referenced_outer]
                        ref_parts.append({"Ref": loop_variable})
                        layer_lookup_key = {"Fn::Join": ["-", ref_parts]}
                    else:
                        layer_lookup_key = {"Ref": loop_variable}
                else:
                    layer_lookup_key = {"Ref": loop_variable}

                existing_layers = properties.get("Layers", [])
                existing_layers.append(
                    {
                        "Fn::GetAtt": [
                            NESTED_STACK_NAME,
                            {"Fn::FindInMap": [layer_mapping_name, layer_lookup_key, "LayerOutputKey"]},
                        ]
                    }
                )
                properties["Layers"] = existing_layers

        return generated_mappings

    @staticmethod
    def _count_dynamic_properties(
        body: Dict,
        loop_variable: str,
        collection_values: List[str],
    ) -> Counter:
        """Count how many resources use each packageable property name dynamically.

        Used to detect collisions where multiple resources in the same ForEach body
        share the same property name (e.g., two resources both with DefinitionUri).
        """
        from samcli.lib.cfn_language_extensions.models import PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES

        count: Counter = Counter()
        for rtk, rt in body.items():
            if isinstance(rtk, str) and rtk.startswith("Fn::ForEach::"):
                continue
            if not isinstance(rt, dict):
                continue
            rtype = rt.get("Type", "")
            rprops = rt.get("Properties", {})
            if not isinstance(rprops, dict):
                continue
            for pname in PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.get(rtype, []):
                pval = rprops.get(pname)
                if pval is not None and contains_loop_variable(pval, loop_variable) and collection_values:
                    count[pname] += 1
        return count

    @staticmethod
    def _build_expanded_key(
        resource_template_key: str,
        loop_variable: str,
        collection_values: List[str],
        outer_context: Optional[List[Tuple[str, List[str]]]],
    ) -> Optional[str]:
        """Build an expanded resource key by substituting the first value from each loop."""
        if not collection_values:
            return None
        expanded_key = resource_template_key
        if outer_context:
            for ovar, ocoll in outer_context:
                if not ocoll:
                    return None
                expanded_key = substitute_loop_variable(expanded_key, ovar, ocoll[0])
        expanded_key = substitute_loop_variable(expanded_key, loop_variable, collection_values[0])
        return expanded_key

    def _collect_dynamic_mapping_entries(
        self,
        resource_template_key: str,
        prop_name: str,
        loop_variable: str,
        collection_values: List[str],
        modified_resources: Dict,
        outer_context: List[Tuple[str, List[str]]],
        referenced_outer_vars: Optional[List[Tuple[str, List[str]]]] = None,
    ) -> Dict[str, Dict[str, str]]:
        """
        Collect Mapping entries for a dynamic artifact property by looking up
        expanded resources in modified_resources.

        For nested ForEach, enumerates all outer value combinations to find
        the fully-expanded resource name.
        """
        mapping_entries: Dict[str, Dict[str, str]] = {}

        for coll_value in collection_values:
            if outer_context:
                self._collect_nested_mapping_entry(
                    resource_template_key,
                    prop_name,
                    loop_variable,
                    coll_value,
                    modified_resources,
                    outer_context,
                    mapping_entries,
                    referenced_outer_vars=referenced_outer_vars,
                )
            else:
                expanded_key = substitute_loop_variable(resource_template_key, loop_variable, coll_value)
                artifact_value = self._get_artifact_value(modified_resources, expanded_key, prop_name)
                if artifact_value is not None:
                    mapping_entries[coll_value] = {prop_name: artifact_value}

        return mapping_entries

    def _collect_nested_mapping_entry(
        self,
        resource_template_key: str,
        prop_name: str,
        loop_variable: str,
        coll_value: str,
        modified_resources: Dict,
        outer_context: List[Tuple[str, List[str]]],
        mapping_entries: Dict[str, Dict[str, str]],
        referenced_outer_vars: Optional[List[Tuple[str, List[str]]]] = None,
    ) -> None:
        """Enumerate outer value combinations to find expanded resource for a nested ForEach."""
        import itertools

        outer_collections = [oc[1] for oc in outer_context]
        outer_vars = [oc[0] for oc in outer_context]

        # Determine which outer vars need compound keys
        compound_outer_vars = {ovar for ovar, _ in (referenced_outer_vars or [])}

        for outer_combo in itertools.product(*outer_collections):
            expanded_key = resource_template_key
            for ovar, oval in zip(outer_vars, outer_combo):
                expanded_key = substitute_loop_variable(expanded_key, ovar, oval)
            expanded_key = substitute_loop_variable(expanded_key, loop_variable, coll_value)

            artifact_value = self._get_artifact_value(modified_resources, expanded_key, prop_name)
            if artifact_value is None:
                continue

            if compound_outer_vars:
                # Build compound key from referenced outer values + inner value
                key_parts = [oval for ovar, oval in zip(outer_vars, outer_combo) if ovar in compound_outer_vars]
                key_parts.append(coll_value)
                mapping_key = "-".join(key_parts)
            else:
                mapping_key = coll_value

            if mapping_key not in mapping_entries:
                mapping_entries[mapping_key] = {prop_name: artifact_value}

    def _collect_foreach_layer_mappings(
        self,
        resource_template_key: str,
        loop_variable: str,
        collection_values: List[str],
        modified_resources: Dict,
        outer_context: List[Tuple[str, List[str]]],
    ) -> Dict[str, Dict[str, str]]:
        """
        Collect Mapping entries for auto dependency layer references by looking up
        expanded resources in modified_resources and extracting their Layers entries
        that reference AwsSamAutoDependencyLayerNestedStack.

        Returns a dict mapping each collection value (or compound key for nested ForEach)
        to its layer output key, e.g. {"Alpha": {"LayerOutputKey": "Outputs.AlphaFunction...DepLayer"}}.
        """
        import itertools

        mapping_entries: Dict[str, Dict[str, str]] = {}

        for coll_value in collection_values:
            if outer_context:
                outer_collections = [oc[1] for oc in outer_context]
                outer_vars = [oc[0] for oc in outer_context]
                for outer_combo in itertools.product(*outer_collections):
                    expanded_key = resource_template_key
                    for ovar, oval in zip(outer_vars, outer_combo):
                        expanded_key = substitute_loop_variable(expanded_key, ovar, oval)
                    expanded_key = substitute_loop_variable(expanded_key, loop_variable, coll_value)

                    layer_output_key = self._extract_nested_stack_layer_output(modified_resources, expanded_key)
                    if layer_output_key is not None:
                        mapping_entries[coll_value] = {"LayerOutputKey": layer_output_key}
                        break
            else:
                expanded_key = substitute_loop_variable(resource_template_key, loop_variable, coll_value)
                layer_output_key = self._extract_nested_stack_layer_output(modified_resources, expanded_key)
                if layer_output_key is not None:
                    mapping_entries[coll_value] = {"LayerOutputKey": layer_output_key}

        return mapping_entries

    @staticmethod
    def _extract_nested_stack_layer_output(modified_resources: Dict, expanded_key: str) -> Optional[str]:
        """
        Extract the layer output key from an expanded resource's Layers property.

        Looks for a Layers entry of the form:
            {"Fn::GetAtt": ["AwsSamAutoDependencyLayerNestedStack", "Outputs.<LayerId>"]}
        and returns the output reference string (e.g. "Outputs.AlphaFunction...DepLayer").
        """
        resource = modified_resources.get(expanded_key)
        if not isinstance(resource, dict):
            return None
        props = resource.get("Properties")
        if not isinstance(props, dict):
            return None
        layers = props.get("Layers")
        if not isinstance(layers, list):
            return None
        for layer_entry in layers:
            if not isinstance(layer_entry, dict):
                continue
            get_att = layer_entry.get("Fn::GetAtt")
            if isinstance(get_att, list) and len(get_att) == 2 and get_att[0] == NESTED_STACK_NAME:  # noqa: PLR2004
                output_key = get_att[1]
                if isinstance(output_key, str):
                    return output_key
        return None

    @staticmethod
    def _get_artifact_value(modified_resources: Dict, expanded_key: str, prop_name: str) -> Optional[Any]:
        """Extract an artifact property value from an expanded resource, or return None."""
        modified_resource = modified_resources.get(expanded_key, {})
        if not isinstance(modified_resource, dict):
            return None
        modified_props = modified_resource.get("Properties", {})
        if not isinstance(modified_props, dict):
            return None
        return modified_props.get(prop_name)

    def _copy_artifact_paths(self, original_resource: Dict, modified_resource: Dict) -> None:
        """
        Copy artifact paths from modified resource to original resource.

        Uses PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES to determine which
        properties to copy, avoiding a hardcoded elif chain.

        Parameters
        ----------
        original_resource : Dict
            The original resource (will be modified in place)
        modified_resource : Dict
            The modified resource with updated artifact paths
        """
        from samcli.lib.cfn_language_extensions.models import PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES

        original_props = original_resource.get("Properties", {})
        modified_props = modified_resource.get("Properties", {})
        resource_type = original_resource.get("Type", "")

        prop_names = PACKAGEABLE_RESOURCE_ARTIFACT_PROPERTIES.get(resource_type)
        if not prop_names:
            return

        for prop_name in prop_names:
            if prop_name in modified_props:
                original_props[prop_name] = modified_props[prop_name]

    def _gen_success_msg(self, artifacts_dir: str, output_template_path: str, is_default_build_dir: bool) -> str:
        """
        Generates a success message containing some suggested commands to run

        Parameters
        ----------
        artifacts_dir: str
            A string path representing the folder of built artifacts
        output_template_path: str
            A string path representing the final template file
        is_default_build_dir: bool
            True if the build folder is the folder defined by SAM CLI

        Returns
        -------
        str
            A formatted success message string
        """

        validate_suggestion = "Validate SAM template: sam validate"
        invoke_suggestion = "Invoke Function: sam local invoke"
        sync_suggestion = "Test Function in the Cloud: sam sync --stack-name {{stack-name}} --watch"
        deploy_suggestion = "Deploy: sam deploy --guided"
        start_lambda_suggestion = "Emulate local Lambda functions: sam local start-lambda"

        if not is_default_build_dir and not self._hook_name:
            invoke_suggestion += " -t {}".format(output_template_path)
            deploy_suggestion += " --template-file {}".format(output_template_path)

        commands = [validate_suggestion, invoke_suggestion, sync_suggestion, deploy_suggestion]

        # check if we have used a hook package before building
        if self._hook_name:
            hook_package_flag = f" --hook-name {self._hook_name}"

            start_lambda_suggestion += hook_package_flag
            invoke_suggestion += hook_package_flag

            commands = [invoke_suggestion, start_lambda_suggestion]

        msg = f"""\nBuilt Artifacts  : {artifacts_dir}
Built Template   : {output_template_path}

Commands you can use next
=========================
"""

        # add bullet point then join all the commands with new line
        msg += "[*] " + f"{os.linesep}[*] ".join(commands)

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

    @property
    def build_result(self) -> Optional[ApplicationBuildResult]:
        return self._build_result

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
            all_resources = [func.name for func in self.function_provider.get_all() if not func.inlinecode]
            all_resources.extend([layer.name for layer in self.layer_provider.get_all()])

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
                func
                for func in self.function_provider.get_all()
                if (func.name not in excludes) and func.function_build_info.is_buildable()
            ]
        )
        result.add_layers(
            [
                layer
                for layer in self.layer_provider.get_all()
                if (layer.name not in excludes) and BuildContext.is_layer_buildable(layer)
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
        resource_collector.add_layers([layer for layer in function.layers if BuildContext.is_layer_buildable(layer)])

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
    def is_layer_buildable(layer: LayerVersion):
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

    _EXCLUDE_WARNING_MESSAGE = "Resource expected to be built, but marked as excluded.\nBuilding anyways..."

    def _check_exclude_warning(self) -> None:
        """
        Prints warning message if a single resource to build is also being excluded
        """
        excludes: Tuple[str, ...] = self._exclude if self._exclude is not None else ()
        if self._resource_identifier in excludes:
            LOG.warning(self._EXCLUDE_WARNING_MESSAGE)

    def _check_build_method_experimental_flag(self) -> None:
        """
        Prints warning message and confirms if user wants to use beta feature
        """
        EXPERIMENTAL_BUILD_METHODS = {
            "rust-cargolambda": ExperimentalFlag.RustCargoLambda,
            "python-uv": ExperimentalFlag.UvPackageManager,
        }

        resources_to_build = self.get_resources_to_build()
        for function in resources_to_build.functions:
            if function.metadata and function.metadata.get("BuildMethod", "") in EXPERIMENTAL_BUILD_METHODS:
                build_method = function.metadata.get("BuildMethod", "")
                WARNING_MESSAGE = (
                    f'Build method "{build_method}" is a beta feature.\n'
                    "Please confirm if you would like to proceed\n"
                    'You can also enable this beta feature with "sam build --beta-features".'
                )

                prompt_experimental(EXPERIMENTAL_BUILD_METHODS[build_method], WARNING_MESSAGE)

    @property
    def build_in_source(self) -> Optional[bool]:
        return self._build_in_source
