"""
Exporting resources defined in the cloudformation template to the cloud.
"""
# pylint: disable=no-member

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
from typing import Dict

from botocore.utils import set_value_from_jmespath

from samcli.commands._utils.resources import (
    AWS_SERVERLESS_FUNCTION,
    AWS_CLOUDFORMATION_STACK,
    RESOURCES_WITH_LOCAL_PATHS,
    AWS_SERVERLESS_APPLICATION,
)
from samcli.commands.package import exceptions
from samcli.lib.package.code_signer import CodeSigner
from samcli.lib.package.packageable_resources import (
    RESOURCES_EXPORT_LIST,
    METADATA_EXPORT_LIST,
    GLOBAL_EXPORT_DICT,
    ResourceZip,
)
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.uploaders import Uploaders
from samcli.lib.package.utils import (
    is_local_folder,
    make_abs_path,
    is_local_file,
    mktempfile,
    is_s3_url,
)
from samcli.lib.utils.packagetype import ZIP
from samcli.yamlhelper import yaml_parse, yaml_dump


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

        exported_template_dict = Template(template_path, parent_dir, self.uploaders, self.code_signer).export()

        exported_template_str = yaml_dump(exported_template_dict)

        with mktempfile() as temporary_file:
            temporary_file.write(exported_template_str)
            temporary_file.flush()

            url = self.uploader.upload_with_dedup(temporary_file.name, "template")

            # TemplateUrl property requires S3 URL to be in path-style format
            parts = S3Uploader.parse_s3_url(url, version_property="Version")
            s3_path_url = self.uploader.to_path_style_s3_url(parts["Key"], parts.get("Version", None))
            set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, s3_path_url)


class ServerlessApplicationResource(CloudFormationStackResource):
    """
    Represents Serverless::Application resource that can refer to a nested
    app template via Location property.
    """

    RESOURCE_TYPE = AWS_SERVERLESS_APPLICATION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[AWS_SERVERLESS_APPLICATION][0]


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
            RESOURCES_EXPORT_LIST + [CloudFormationStackResource, ServerlessApplicationResource]
        ),
        metadata_to_export=frozenset(METADATA_EXPORT_LIST),
    ):
        """
        Reads the template and makes it ready for export
        """
        if not (is_local_folder(parent_dir) and os.path.isabs(parent_dir)):
            raise ValueError("parent_dir parameter must be " "an absolute path to a folder {0}".format(parent_dir))

        abs_template_path = make_abs_path(parent_dir, template_path)
        template_dir = os.path.dirname(abs_template_path)

        with open(abs_template_path, "r") as handle:
            template_str = handle.read()

        self.template_dict = yaml_parse(template_str)
        self.template_dir = template_dir
        self.resources_to_export = resources_to_export
        self.metadata_to_export = metadata_to_export
        self.uploaders = uploaders
        self.code_signer = code_signer

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

        for resource_id, resource in self.template_dict["Resources"].items():

            resource_type = resource.get("Type", None)
            resource_dict = resource.get("Properties", {})

            for exporter_class in self.resources_to_export:
                if exporter_class.RESOURCE_TYPE != resource_type:
                    continue
                if resource_dict.get("PackageType", ZIP) != exporter_class.ARTIFACT_TYPE:
                    continue
                # Export code resources
                exporter = exporter_class(self.uploaders, self.code_signer)
                exporter.export(resource_id, resource_dict, self.template_dir)

        return self.template_dict
