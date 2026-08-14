"""
Exporting resources defined in the cloudformation template to the cloud.
"""

# Copyright 2012-2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
import copy
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, cast

from botocore.utils import set_value_from_jmespath

from samcli.commands._utils.experimental import ExperimentalFlag, is_experimental_enabled
from samcli.commands.package import exceptions
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.cfn_language_extensions.sam_integration import expand_language_extensions
from samcli.lib.cfn_language_extensions.utils import iter_regular_resources
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.package.code_signer import CodeSigner
from samcli.lib.package.language_extensions_packaging import (
    generate_and_apply_artifact_mappings,
    merge_language_extensions_s3_uris,
)
from samcli.lib.package.local_files_utils import get_uploaded_s3_object_name, mktempfile
from samcli.lib.package.packageable_resources import (
    GLOBAL_TRANSFORM_EXPORTS,
    METADATA_EXPORTS,
    RESOURCES_EXPORT_LIST,
    ECRResource,
    MetadataExportSpec,
    ResourceZip,
)
from samcli.lib.package.uploaders import Destination, Uploaders
from samcli.lib.package.utils import (
    is_local_file,
    is_local_folder,
    is_s3_url,
    make_abs_path,
)
from samcli.lib.providers.provider import get_full_path
from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer
from samcli.lib.utils.packagetype import ZIP
from samcli.lib.utils.resources import (
    AWS_CLOUDFORMATION_STACK,
    AWS_CLOUDFORMATION_STACKSET,
    AWS_SERVERLESS_APPLICATION,
    AWS_SERVERLESS_FUNCTION,
    RESOURCES_WITH_LOCAL_PATHS,
)
from samcli.lib.utils.s3 import parse_s3_url
from samcli.yamlhelper import yaml_dump, yaml_parse

LOG = logging.getLogger(__name__)

# NOTE: sriram-mv, A cyclic dependency on `Template` needs to be broken.


def _resolve_nested_stack_parameters(nested_params: Dict, parent_parameter_values: Dict) -> Dict:
    """
    Resolve intrinsics in the nested stack resource's Parameters property using
    the parent's parameter context.

    Values that cannot be resolved locally (e.g. Fn::GetAtt, Fn::ImportValue,
    Ref to a parent resource) are dropped — the child's own Parameter.Default
    or a later processing step will handle them. This keeps package-time
    expansion best-effort without raising on templates that cross-reference
    runtime-only values.
    """
    if not nested_params:
        return {}
    # Local imports to preserve existing import ordering and avoid a cycle at load time.
    from samcli.lib.cfn_language_extensions.api import create_default_intrinsic_resolver
    from samcli.lib.cfn_language_extensions.exceptions import (
        InvalidTemplateException,
        UnresolvableReferenceError,
    )
    from samcli.lib.cfn_language_extensions.models import (
        ResolutionMode,
        TemplateProcessingContext,
    )

    ctx = TemplateProcessingContext(
        fragment={},
        parameter_values=parent_parameter_values or {},
        resolution_mode=ResolutionMode.PARTIAL,
    )
    resolver = create_default_intrinsic_resolver(ctx)

    resolved: Dict = {}
    for name, value in nested_params.items():
        try:
            resolved_value = resolver.resolve_value(value)
        except (UnresolvableReferenceError, InvalidTemplateException):
            # Expected: the nested-stack parameter references something the
            # resolver can't see at package time (e.g. a sibling resource).
            continue
        except Exception as e:  # pylint: disable=broad-except
            # Unexpected — likely a SAM CLI bug. Log with traceback so
            # --debug surfaces it; drop the value so packaging still proceeds.
            LOG.warning(
                "Unexpected error resolving nested stack parameter %r; skipping: %s. "
                "Run with --debug for the full traceback.",
                name,
                e,
            )
            LOG.debug("Traceback for parameter %r resolution failure:", name, exc_info=True)
            continue
        # Drop values that still contain intrinsics (unresolvable at package time).
        if isinstance(resolved_value, dict) and len(resolved_value) == 1:
            only_key = next(iter(resolved_value))
            if only_key == "Ref" or only_key.startswith("Fn::"):
                continue
        resolved[name] = resolved_value
    return resolved


def _build_child_parameter_values(
    parent_parameter_values: Optional[Dict],
    nested_stack_parameters: Dict,
) -> Dict:
    """Build the parameter_values dict the LE expander should see for a child stack.

    CFN-parity scope: pseudo-params (with parent overrides for the pseudo NAMES
    only) and the parent's explicit rebindings via the nested-stack ``Parameters``
    property. Non-pseudo parent names are NOT copied — that would diverge from
    CloudFormation's nested-stack contract.

    Child template ``Parameters.X.Default`` values are NOT folded in here. The
    LE expander's Fn::Ref resolver reads them itself from
    ``context.parsed_template.parameters[X]["Default"]``, which
    ``TemplateParsingProcessor`` populates as the first step of the expansion
    pipeline. So Defaults still take effect at expansion time; they just don't
    pass through this helper's return value.

    Names declared in the child but neither defaulted nor rebound are
    intentionally absent everywhere — PARTIAL mode preserves the Ref and
    CloudFormation errors at deploy time, matching the non-LE path.
    """
    parameter_values: Dict = dict(IntrinsicsSymbolTable.DEFAULT_PSEUDO_PARAM_VALUES)

    if parent_parameter_values:
        for pseudo_name in IntrinsicsSymbolTable.DEFAULT_PSEUDO_PARAM_VALUES:
            if pseudo_name in parent_parameter_values:
                parameter_values[pseudo_name] = parent_parameter_values[pseudo_name]

    resolved_nested = _resolve_nested_stack_parameters(
        nested_stack_parameters,
        dict(parent_parameter_values or {}),
    )
    parameter_values.update(resolved_nested)

    return parameter_values


def _export_global_artifacts_pass(template_dict: Any, uploader, template_dir: str) -> Any:
    """
    Walk template_dict recursively, dispatching dict nodes to handlers
    registered in GLOBAL_TRANSFORM_EXPORTS (today: AWS::Include).

    Mutates template_dict in place AND returns it for caller convenience.

    This is the standalone form of Template._export_global_artifacts —
    used by callers that need to run the global-transform export pass
    on a template before constructing a Template (e.g., the pre-LE
    pass that processes AWS::Include before language-extension
    expansion runs).

    No-ops on non-dict input (e.g. yaml_parse returning None for empty
    template files), so callers can pass the result of yaml_parse
    unconditionally.
    """
    if not isinstance(template_dict, dict):
        return template_dict

    specs_by_key: Dict[str, list] = {}
    for spec in GLOBAL_TRANSFORM_EXPORTS:
        specs_by_key.setdefault(spec.template_key, []).append(spec)

    for key, val in template_dict.items():
        if key in specs_by_key:
            current = val
            for spec in specs_by_key[key]:
                if spec.discriminator(current):
                    template_dict[key] = spec.handler(current, uploader, template_dir)
                    current = template_dict[key]
        elif isinstance(val, dict):
            _export_global_artifacts_pass(val, uploader, template_dir)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _export_global_artifacts_pass(item, uploader, template_dir)
    return template_dict


class CloudFormationStackResource(ResourceZip):
    """
    Represents CloudFormation::Stack resource that can refer to a nested
    stack template via TemplateURL property.
    """

    RESOURCE_TYPE = AWS_CLOUDFORMATION_STACK
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    parent_parameter_values: Optional[Dict] = None
    language_extensions_enabled: bool = False

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        If the nested stack template is valid, this method will
        export on the nested template, upload the exported template to S3
        and set property to URL of the uploaded S3 template.

        Routes to the LE-on or LE-off branch based on
        self.language_extensions_enabled. The flag is a hard structural
        gate — when off, no language-extension machinery runs.
        """
        template_path = resource_dict.get(self.PROPERTY_NAME, None)

        if template_path is None or is_s3_url(template_path):
            # Nothing to do
            return

        abs_template_path = make_abs_path(parent_dir, template_path)
        if not is_local_file(abs_template_path):
            raise exceptions.InvalidTemplateUrlParameterError(
                property_name=self.PROPERTY_NAME, resource_id=resource_id, template_path=abs_template_path
            )

        if self.language_extensions_enabled:
            exported_template_dict = self._do_export_with_language_extensions(
                resource_id,
                template_path,
                parent_dir,
                abs_template_path,
                resource_dict,
            )
        else:
            exported_template_dict = self._do_export_without_language_extensions(resource_id, template_path, parent_dir)

        exported_template_str = yaml_dump(exported_template_dict)

        with mktempfile() as temporary_file:
            temporary_file.write(exported_template_str)
            temporary_file.flush()
            remote_path = get_uploaded_s3_object_name(file_path=temporary_file.name, extension="template")
            url = self.uploader.upload(temporary_file.name, remote_path)

            # TemplateUrl property requires S3 URL to be in path-style format
            parts = parse_s3_url(url, version_property="Version")
            s3_path_url = self.uploader.to_path_style_s3_url(parts["Key"], parts.get("Version", None))
            set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, s3_path_url)

    def _do_export_without_language_extensions(self, resource_id: str, template_path: str, parent_dir: str) -> Dict:
        """LE-off branch: legacy path-based Template construction.

        Template.export() runs its own internal _export_global_artifacts so
        AWS::Include still resolves on this path. No pre-LE pass, no
        parameter_values, no parent_parameter_values, no copy.deepcopy —
        none of them are needed without language extensions.
        """
        return Template(
            template_path,
            parent_dir,
            self.uploaders,
            self.code_signer,
            normalize_template=True,
            normalize_parameters=True,
            parent_stack_id=resource_id,
            language_extensions_enabled=False,
        ).export()

    def _do_export_with_language_extensions(
        self,
        resource_id: str,
        template_path: str,
        parent_dir: str,
        abs_template_path: str,
        resource_dict: Dict,
    ) -> Dict:
        """LE-on branch: dict-based Template construction with full LE machinery.

        Reads the child template to a dict, runs the pre-LE AWS::Include pass
        (#9027), threads pseudo-params + parent_parameter_values + nested
        Parameters into expand_language_extensions, and merges S3 URIs back
        if expansion produced any.

        Falls back to the no-extensions path for InvalidSamDocumentException
        (expected user-facing failure) and unexpected exceptions (SAM CLI
        bugs — logged at ERROR with traceback).
        """
        with open(abs_template_path, "r", encoding="utf-8") as f:
            child_template_dict = yaml_parse(f.read())

        child_template_dir = os.path.dirname(abs_template_path)

        # Process AWS::Include before LE expansion to mirror CFN's transform
        # ordering. See aws/aws-sam-cli#9027.
        #
        # NOTE: mutates child_template_dict in place. Must run before the
        # expand_language_extensions call below so result.original_template
        # and result.expanded_template both observe the rewrite.
        _export_global_artifacts_pass(
            child_template_dict,
            self.uploaders.get(ResourceZip.EXPORT_DESTINATION),
            child_template_dir,
        )

        parameter_values = _build_child_parameter_values(
            self.parent_parameter_values,
            resource_dict.get("Parameters", {}) or {},
        )

        try:
            result = expand_language_extensions(
                child_template_dict,
                parameter_values,
                enabled=self.language_extensions_enabled,
            )
        except InvalidSamDocumentException as e:
            # Expected failure path: the child template triggered the
            # AWS::LanguageExtensions transform but SAM CLI could not expand it
            # locally. Defer to CloudFormation's server-side transform. Note: any
            # artifact paths inside Fn::ForEach bodies will NOT be uploaded, so
            # child stacks with dynamic artifact properties (e.g. CodeUri using a
            # loop variable) will fail at deploy time.
            LOG.warning(
                "Language extensions expansion failed for %s. "
                "CloudFormation will process the AWS::LanguageExtensions transform "
                "server-side; artifact URIs inside Fn::ForEach blocks will NOT be "
                "uploaded. Error: %s",
                abs_template_path,
                e,
            )
            result = None
        except Exception as e:  # pylint: disable=broad-except
            LOG.error(
                "Internal error expanding language extensions for %s. This is a "
                "SAM CLI bug; please report at "
                "https://github.com/aws/aws-sam-cli/issues with the template. "
                "Falling back to server-side transform. Error: %s",
                abs_template_path,
                e,
                exc_info=True,
            )
            result = None

        if result and result.had_language_extensions:
            LOG.debug(
                "Child template %s uses language extensions, expanding before export",
                abs_template_path,
            )

            template = Template(
                template_path,
                parent_dir,
                self.uploaders,
                self.code_signer,
                normalize_template=True,
                normalize_parameters=True,
                parent_stack_id=resource_id,
                template_dict=copy.deepcopy(result.expanded_template),
                parameter_values=parameter_values,
                language_extensions_enabled=self.language_extensions_enabled,
            )

            exported_template = template.export()

            exported_template_dict = merge_language_extensions_s3_uris(
                result.original_template,
                exported_template,
                result.dynamic_artifact_properties,
            )

            if result.dynamic_artifact_properties:
                LOG.debug(
                    "Generating Mappings for %d dynamic artifact properties in child template",
                    len(result.dynamic_artifact_properties),
                )
                exported_resources = exported_template.get("Resources", {})
                exported_template_dict = generate_and_apply_artifact_mappings(
                    exported_template_dict,
                    result.dynamic_artifact_properties,
                    exported_resources,
                    child_template_dir,
                )
        else:
            exported_template_dict = Template(
                template_path,
                parent_dir,
                self.uploaders,
                self.code_signer,
                normalize_template=True,
                normalize_parameters=True,
                parent_stack_id=resource_id,
                parameter_values=parameter_values,
                language_extensions_enabled=self.language_extensions_enabled,
            ).export()

        return exported_template_dict


class ServerlessApplicationResource(CloudFormationStackResource):
    """
    Represents Serverless::Application resource that can refer to a nested
    app template via Location property.
    """

    RESOURCE_TYPE = AWS_SERVERLESS_APPLICATION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[AWS_SERVERLESS_APPLICATION][0]


class CloudFormationStackSetResource(ResourceZip):
    """
    Represents CloudFormation::StackSet resource that can refer to a
    stack template via TemplateURL property.
    """

    RESOURCE_TYPE = AWS_CLOUDFORMATION_STACKSET
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        If the stack template is valid, this method will
        upload the template to S3
        and set property to URL of the uploaded S3 template
        """

        template_path = resource_dict.get(self.PROPERTY_NAME, None)

        if template_path is None or is_s3_url(template_path):
            # Nothing to do
            return

        abs_template_path = make_abs_path(parent_dir, template_path)
        if not is_local_file(abs_template_path):
            raise exceptions.InvalidTemplateUrlParameterError(
                property_name=self.PROPERTY_NAME, resource_id=resource_id, template_path=abs_template_path
            )

        remote_path = get_uploaded_s3_object_name(file_path=abs_template_path, extension="template")
        url = self.uploader.upload(abs_template_path, remote_path)

        # TemplateUrl property requires S3 URL to be in path-style format
        parts = parse_s3_url(url, version_property="Version")
        s3_path_url = self.uploader.to_path_style_s3_url(parts["Key"], parts.get("Version", None))
        set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, s3_path_url)


class Template:
    """
    Class to export a CloudFormation template
    """

    template_dict: Dict
    template_dir: str
    resources_to_export: frozenset
    metadata_to_export: Sequence[MetadataExportSpec]
    uploaders: Uploaders
    code_signer: CodeSigner

    def __init__(
        self,
        template_path: str,
        parent_dir: str,
        uploaders: Uploaders,
        code_signer: CodeSigner,
        resources_to_export=frozenset(
            RESOURCES_EXPORT_LIST
            + [CloudFormationStackResource, CloudFormationStackSetResource, ServerlessApplicationResource]
        ),
        metadata_to_export=tuple(METADATA_EXPORTS),
        template_str: Optional[str] = None,
        normalize_template: bool = False,
        normalize_parameters: bool = False,
        parent_stack_id: str = "",
        parameter_values: Optional[Dict] = None,
        template_dict: Optional[Dict] = None,
        language_extensions_enabled: bool = False,
    ):
        """
        Reads the template and makes it ready for export
        """
        if template_dict is not None:
            # Pre-parsed dict provided — skip file reading and YAML parsing.
            self.template_dict = template_dict
            self.template_dir = (
                os.path.dirname(os.path.abspath(make_abs_path(parent_dir, template_path)))
                if parent_dir
                else os.getcwd()
            )
            self.code_signer = code_signer
        elif template_str:
            self.template_dict = yaml_parse(template_str)
            self.template_dir = (
                os.path.dirname(os.path.abspath(make_abs_path(parent_dir, template_path)))
                if parent_dir
                else os.getcwd()
            )
            self.code_signer = code_signer
        else:
            if not (is_local_folder(parent_dir) and os.path.isabs(parent_dir)):
                raise ValueError("parent_dir parameter must be an absolute path to a folder {0}".format(parent_dir))

            abs_template_path = make_abs_path(parent_dir, template_path)
            template_dir = os.path.dirname(abs_template_path)

            with open(abs_template_path, "r", encoding="utf-8") as handle:
                template_str = handle.read()

            self.template_dir = template_dir
            self.code_signer = code_signer
            self.template_dict = yaml_parse(template_str)
        if normalize_template:
            ResourceMetadataNormalizer.normalize(self.template_dict, normalize_parameters)
        self.resources_to_export = resources_to_export
        self.metadata_to_export = metadata_to_export
        self.uploaders = uploaders
        self.parent_stack_id = parent_stack_id
        # Parameter values to pass down to child-template expansion (e.g. Fn::ForEach
        # collections that Ref a parameter). None preserves pre-existing behavior.
        self.parameter_values = parameter_values
        self.language_extensions_enabled = language_extensions_enabled

    def _export_global_artifacts(self, template_dict: Dict) -> Dict:
        """See module-level _export_global_artifacts_pass for the canonical
        implementation. This wrapper exists so Template.export() doesn't
        need to know about uploader / template_dir plumbing.
        """
        result = _export_global_artifacts_pass(
            template_dict,
            self.uploaders.get(ResourceZip.EXPORT_DESTINATION),
            self.template_dir,
        )
        # template_dict is guaranteed to be a dict here, so the pass returns
        # the same dict back. cast() narrows the return type for mypy.
        return cast(Dict, result)

    def _export_metadata(self):
        """
        Exports the local artifacts referenced by the metadata section in
        the given template to an export destination.
        """
        if "Metadata" not in self.template_dict:
            return

        specs_by_type = {spec.metadata_type: spec for spec in self.metadata_to_export}

        for metadata_type, metadata_dict in self.template_dict["Metadata"].items():
            spec = specs_by_type.get(metadata_type)
            if spec is None:
                continue
            for exporter_class in spec.exporters:
                exporter = exporter_class(self.uploaders, self.code_signer)
                exporter.export(metadata_type, metadata_dict, self.template_dir)

    def _apply_global_values(self):
        """
        Takes values from the "Global" parameters and applies them to resources where needed for packaging.

        This transform method addresses issue 1706, where CodeUri is expected to be allowed as a global param for
        packaging, even when there may not be a build step (such as the source being an S3 file). This is the only
        known use case for using any global values in the package step, so any other such global value applications
        should be scoped to this method if possible.

        Intentionally not dealing with Api:DefinitionUri at this point.
        """
        for resource_key, resource in iter_regular_resources(self.template_dict):
            resource_type = resource.get("Type", None)
            resource_dict = resource.get("Properties", None)

            if resource_dict is not None:
                if "CodeUri" not in resource_dict and resource_type == AWS_SERVERLESS_FUNCTION:
                    code_uri_global = self.template_dict.get("Globals", {}).get("Function", {}).get("CodeUri", None)
                    if code_uri_global is not None and resource_dict is not None:
                        resource_dict["CodeUri"] = code_uri_global

    def export(self) -> Dict:
        """
        Exports the local artifacts referenced by the given template to an
        export destination.

        :return: The template with references to artifacts that have been
        exported to an export destination.
        """
        self._export_metadata()

        if "Resources" not in self.template_dict:
            return self.template_dict

        self._apply_global_values()
        self.template_dict = self._export_global_artifacts(self.template_dict)

        cache: Optional[Dict] = None
        if is_experimental_enabled(ExperimentalFlag.PackagePerformance):
            cache = {}

        for resource_logical_id, resource in iter_regular_resources(self.template_dict):
            resource_type = resource.get("Type", None)
            resource_dict = resource.get("Properties", {})
            resource_id = ResourceMetadataNormalizer.get_resource_id(resource, resource_logical_id)
            full_path = get_full_path(self.parent_stack_id, resource_id)

            for exporter_class in self.resources_to_export:
                if exporter_class.RESOURCE_TYPE != resource_type:
                    continue
                if resource_dict.get("PackageType", ZIP) != exporter_class.ARTIFACT_TYPE:
                    continue
                # Export code resources
                exporter = exporter_class(self.uploaders, self.code_signer, cache)
                exporter.parent_parameter_values = self.parameter_values
                exporter.language_extensions_enabled = self.language_extensions_enabled
                exporter.export(full_path, resource_dict, self.template_dir)

        return self.template_dict

    def delete(self, retain_resources: List):
        """
        Deletes all the artifacts referenced by the given Cloudformation template
        """
        if "Resources" not in self.template_dict:
            return

        self._apply_global_values()

        for resource_id, resource in iter_regular_resources(self.template_dict):
            resource_type = resource.get("Type", None)
            resource_dict = resource.get("Properties", {})
            resource_deletion_policy = resource.get("DeletionPolicy", None)
            # If the deletion policy is set to Retain,
            # do not delete the artifact for the resource.
            if resource_deletion_policy != "Retain" and resource_id not in retain_resources:
                for exporter_class in self.resources_to_export:
                    if exporter_class.RESOURCE_TYPE != resource_type:
                        continue
                    if resource_dict.get("PackageType", ZIP) != exporter_class.ARTIFACT_TYPE:
                        continue
                    # Delete code resources
                    exporter = exporter_class(self.uploaders, None)
                    exporter.delete(resource_id, resource_dict)

    def get_ecr_repos(self):
        """
        Get all the ecr repos from the template
        """
        ecr_repos = {}
        if "Resources" not in self.template_dict:
            return ecr_repos

        self._apply_global_values()
        for resource_id, resource in iter_regular_resources(self.template_dict):
            resource_type = resource.get("Type", None)
            resource_dict = resource.get("Properties", {})
            resource_deletion_policy = resource.get("DeletionPolicy", None)
            if resource_deletion_policy == "Retain" or resource_type != "AWS::ECR::Repository":
                continue

            ecr_resource = ECRResource(self.uploaders, None)
            ecr_repos[resource_id] = {"Repository": ecr_resource.get_property_value(resource_dict)}

        return ecr_repos

    def get_s3_info(self):
        """
        Iterates the template_dict resources with S3 EXPORT_DESTINATION to get the
        s3_bucket and s3_prefix information for the purpose of deletion.
        Method finds the first resource with s3 information, extracts the information
        and then terminates. It is safe to assume that all the packaged files using the
        commands package and deploy are in the same s3 bucket with the same s3 prefix.
        """
        result = {"s3_bucket": None, "s3_prefix": None}
        if "Resources" not in self.template_dict:
            return result

        self._apply_global_values()

        for resource_key, resource in iter_regular_resources(self.template_dict):
            resource_type = resource.get("Type", None)
            resource_dict = resource.get("Properties", {})

            for exporter_class in self.resources_to_export:
                # Skip the resources which don't give s3 information
                if exporter_class.EXPORT_DESTINATION != Destination.S3:
                    continue
                if exporter_class.RESOURCE_TYPE != resource_type:
                    continue
                if resource_dict.get("PackageType", ZIP) != exporter_class.ARTIFACT_TYPE:
                    continue

                exporter = exporter_class(self.uploaders, None)
                s3_info = exporter.get_property_value(resource_dict)

                result["s3_bucket"] = s3_info["Bucket"]
                s3_key = s3_info["Key"]

                # Extract the prefix from the key
                if s3_key:
                    key_split = s3_key.rsplit("/", 1)
                    if len(key_split) > 1:
                        result["s3_prefix"] = key_split[0]
                break
            if result["s3_bucket"]:
                break

        return result
