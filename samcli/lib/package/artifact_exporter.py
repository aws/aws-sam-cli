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
import os
from typing import Dict, List, Optional

from botocore.utils import set_value_from_jmespath

from samcli.commands.package import exceptions
from samcli.lib.package.code_signer import CodeSigner
from samcli.lib.package.local_files_utils import get_uploaded_s3_object_name, mktempfile
from samcli.lib.package.packageable_resources import (
    GLOBAL_EXPORT_DICT,
    METADATA_EXPORT_LIST,
    RESOURCES_EXPORT_LIST,
    ECRResource,
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

# NOTE: sriram-mv, A cyclic dependency on `Template` needs to be broken.


class CloudFormationStackResource(ResourceZip):
    """
    Represents CloudFormation::Stack resource that can refer to a nested
    stack template via TemplateURL property.
    """

    RESOURCE_TYPE = AWS_CLOUDFORMATION_STACK
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        If the nested stack template is valid, this method will
        export on the nested template, upload the exported template to S3
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

        exported_template_dict = Template(
            template_path,
            parent_dir,
            self.uploaders,
            self.code_signer,
            normalize_template=True,
            normalize_parameters=True,
            parent_stack_id=resource_id,
        ).export()

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
    metadata_to_export: frozenset
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
        metadata_to_export=frozenset(METADATA_EXPORT_LIST),
        template_str: Optional[str] = None,
        normalize_template: bool = False,
        normalize_parameters: bool = False,
        parent_stack_id: str = "",
    ):
        """
        Reads the template and makes it ready for export
        """
        if not template_str:
            if not (is_local_folder(parent_dir) and os.path.isabs(parent_dir)):
                raise ValueError("parent_dir parameter must be an absolute path to a folder {0}".format(parent_dir))

            abs_template_path = make_abs_path(parent_dir, template_path)
            template_dir = os.path.dirname(abs_template_path)

            with open(abs_template_path, "r") as handle:
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

    def _export_global_artifacts(self, template_dict: Dict) -> Dict:
        """
        Template params such as AWS::Include transforms are not specific to
        any resource type but contain artifacts that should be exported,
        here we iterate through the template dict and export params with a
        handler defined in GLOBAL_EXPORT_DICT
        """
        for key, val in template_dict.items():
            if key in GLOBAL_EXPORT_DICT:
                template_dict[key] = GLOBAL_EXPORT_DICT[key](
                    val, self.uploaders.get(ResourceZip.EXPORT_DESTINATION), self.template_dir
                )
            elif isinstance(val, dict):
                self._export_global_artifacts(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        self._export_global_artifacts(item)
        return template_dict

    def _export_metadata(self):
        """
        Exports the local artifacts referenced by the metadata section in
        the given template to an export destination.
        """
        if "Metadata" not in self.template_dict:
            return

        for metadata_type, metadata_dict in self.template_dict["Metadata"].items():
            for exporter_class in self.metadata_to_export:
                if exporter_class.RESOURCE_TYPE != metadata_type:
                    continue

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
        for _, resource in self.template_dict["Resources"].items():
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

        for resource_logical_id, resource in self.template_dict["Resources"].items():
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
                exporter = exporter_class(self.uploaders, self.code_signer)
                exporter.export(full_path, resource_dict, self.template_dir)

        return self.template_dict

    def delete(self, retain_resources: List):
        """
        Deletes all the artifacts referenced by the given Cloudformation template
        """
        if "Resources" not in self.template_dict:
            return

        self._apply_global_values()

        for resource_id, resource in self.template_dict["Resources"].items():
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
        for resource_id, resource in self.template_dict["Resources"].items():
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

        for _, resource in self.template_dict["Resources"].items():
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
