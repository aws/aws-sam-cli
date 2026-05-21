"""
Logic for uploading to s3 based on supplied template file and s3 bucket
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
import json
import logging
import os
from typing import List, Optional

import boto3
import click

from samcli.commands.package.exceptions import PackageFailedError
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.bootstrap.companion_stack.companion_stack_manager import sync_ecr_stack
from samcli.lib.cfn_language_extensions.sam_integration import (
    expand_language_extensions,
    resolve_language_extensions_enabled,
)
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.package.artifact_exporter import Template, _export_global_artifacts_pass
from samcli.lib.package.code_signer import CodeSigner
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.package.language_extensions_packaging import (
    generate_and_apply_artifact_mappings,
    merge_language_extensions_s3_uris,
)
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.uploaders import Destination, Uploaders
from samcli.lib.providers.provider import ResourceIdentifier, Stack, get_resource_full_path_by_id
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.boto_utils import get_boto_config_with_user_agent
from samcli.lib.utils.preview_runtimes import PREVIEW_RUNTIMES
from samcli.lib.utils.resources import AWS_LAMBDA_FUNCTION, AWS_SERVERLESS_FUNCTION
from samcli.yamlhelper import yaml_dump, yaml_parse

LOG = logging.getLogger(__name__)


class PackageContext:
    MSG_PACKAGED_TEMPLATE_WRITTEN = (
        "\nSuccessfully packaged artifacts and wrote output template "
        "to file {output_file_name}."
        "\n"
        "Execute the following command to deploy the packaged template"
        "\n"
        "sam deploy --template-file {output_file_path} "
        "--stack-name <YOUR STACK NAME>"
        "\n"
    )

    uploaders: Uploaders

    def __init__(
        self,
        template_file,
        s3_bucket,
        image_repository,
        image_repositories,
        s3_prefix,
        kms_key_id,
        output_template_file,
        use_json,
        force_upload,
        no_progressbar,
        metadata,
        region,
        profile,
        parameter_overrides=None,
        on_deploy=False,
        signing_profiles=None,
        resolve_image_repos=False,
        language_extensions=None,
    ):
        self.template_file = template_file
        self.s3_bucket = s3_bucket
        self.image_repository = image_repository
        self.image_repositories = image_repositories
        self.s3_prefix = s3_prefix
        self.kms_key_id = kms_key_id
        self.output_template_file = output_template_file
        self.use_json = use_json
        self.force_upload = force_upload
        self.no_progressbar = no_progressbar
        self.metadata = metadata
        self.region = region
        self.profile = profile
        self.on_deploy = on_deploy
        self.code_signer = None
        self.signing_profiles = signing_profiles
        self.parameter_overrides = parameter_overrides
        self.resolve_image_repos = resolve_image_repos
        self._language_extensions_enabled: bool = resolve_language_extensions_enabled(language_extensions)
        self._global_parameter_overrides = {IntrinsicsSymbolTable.AWS_REGION: region} if region else {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self):
        """
        Execute packaging based on the argument provided by customers and samconfig.toml.
        """
        if self.resolve_image_repos:
            template_basename = os.path.splitext(os.path.basename(self.template_file))[0]
            stack_name = f"sam-app-{template_basename}"

            self.image_repositories = sync_ecr_stack(
                self.template_file, stack_name, self.region, self.s3_bucket, self.s3_prefix, self.image_repositories
            )

        stacks, _ = SamLocalStackProvider.get_stacks(
            self.template_file,
            global_parameter_overrides=self._global_parameter_overrides,
            parameter_overrides=self.parameter_overrides,
            language_extensions_enabled=self._language_extensions_enabled,
        )
        self._warn_preview_runtime(stacks)
        self.image_repositories = self.image_repositories if self.image_repositories is not None else {}
        updated_repo = {}
        for image_repo_func_id, image_repo_uri in self.image_repositories.items():
            repo_full_path = get_resource_full_path_by_id(stacks, ResourceIdentifier(image_repo_func_id))
            if repo_full_path:
                updated_repo[repo_full_path] = image_repo_uri
        self.image_repositories = updated_repo
        region_name = self.region if self.region else None

        s3_client = boto3.client(
            "s3",
            config=get_boto_config_with_user_agent(signature_version="s3v4", region_name=region_name),
        )
        ecr_client = boto3.client("ecr", config=get_boto_config_with_user_agent(region_name=region_name))

        # Pass None instead of validating Docker client upfront - ECRUploader will validate only when needed
        docker_client = None

        s3_uploader = S3Uploader(
            s3_client, self.s3_bucket, self.s3_prefix, self.kms_key_id, self.force_upload, self.no_progressbar
        )
        # attach the given metadata to the artifacts to be uploaded
        s3_uploader.artifact_metadata = self.metadata
        ecr_uploader = ECRUploader(
            docker_client, ecr_client, self.image_repository, self.image_repositories, self.no_progressbar
        )

        self.uploaders = Uploaders(s3_uploader, ecr_uploader)

        code_signer_client = boto3.client("signer", config=get_boto_config_with_user_agent(region_name=region_name))
        self.code_signer = CodeSigner(code_signer_client, self.signing_profiles)

        try:
            exported_str = self._export(self.template_file, self.use_json)

            self.write_output(self.output_template_file, exported_str)

            if self.output_template_file and not self.on_deploy:
                msg = self.MSG_PACKAGED_TEMPLATE_WRITTEN.format(
                    output_file_name=self.output_template_file,
                    output_file_path=os.path.abspath(self.output_template_file),
                )
                click.echo(msg)
        except OSError as ex:
            raise PackageFailedError(template_file=self.template_file, ex=str(ex)) from ex

    def _export(self, template_path, use_json):
        # Read + parse once. Branch methods receive the parsed dict and
        # return the output dict; this dispatcher owns the I/O bookends.
        with open(template_path, "r", encoding="utf-8") as f:
            original_template_dict = yaml_parse(f.read())

        # Structural fork on the opt-in flag (#9033). When LE is disabled
        # we never invoke any LE machinery — no expand_language_extensions,
        # no pre-LE _export_global_artifacts_pass, no merge or Mappings.
        # See aws/aws-sam-cli#9027 for why the on path needs the pre-LE pass.
        if self._language_extensions_enabled:
            output_template = self._export_with_language_extensions(template_path, original_template_dict)
        else:
            output_template = self._export_without_language_extensions(template_path, original_template_dict)

        if use_json:
            return json.dumps(output_template, indent=4, ensure_ascii=False)
        return yaml_dump(output_template)

    def _export_without_language_extensions(self, template_path, original_template_dict):
        """Export a template with AWS::LanguageExtensions opt-in disabled.

        Mirrors pre-1.160.0 sam-cli behavior: AWS::Include and other global
        Fn::Transform exporters are handled inside Template.export() via its
        own _export_global_artifacts pass — no pre-Template pass is needed
        because there is no LE expansion step that would collapse Fn::Transform
        into a JSON-string literal first (see aws/aws-sam-cli#9027 for why the
        LE path differs).
        """
        template = Template(
            template_path,
            os.getcwd(),
            self.uploaders,
            self.code_signer,
            normalize_template=True,
            normalize_parameters=True,
            template_dict=original_template_dict,
            language_extensions_enabled=False,
        )
        return template.export()

    def _export_with_language_extensions(self, template_path, original_template_dict):
        """Export a template with AWS::LanguageExtensions processing enabled.

        Order matters here:
          1. Run AWS::Include (and any other GLOBAL_TRANSFORM_EXPORTS) on the
             original template *before* LE expansion. LE functions like
             Fn::ToJsonString json.dumps() their argument and collapse any
             structural Fn::Transform subtree into a JSON-string literal,
             which would hide the include from the post-export walker.
             See aws/aws-sam-cli#9027.
          2. Run expand_language_extensions to materialize Fn::ForEach,
             Fn::ToJsonString, etc. into a flat resource list.
          3. Run Template.export() on the expanded copy.
          4. Merge the S3 URIs back into the original Fn::ForEach structure
             and apply Mappings for any dynamic artifact properties.
        """
        template_dir = os.path.dirname(os.path.abspath(template_path))
        _export_global_artifacts_pass(
            original_template_dict,
            self.uploaders.get(Destination.S3),
            template_dir,
        )

        parameter_values = {**IntrinsicsSymbolTable.DEFAULT_PSEUDO_PARAM_VALUES}
        if self.parameter_overrides:
            parameter_values.update(self.parameter_overrides)
        if self._global_parameter_overrides:
            parameter_values.update(self._global_parameter_overrides)

        try:
            result = expand_language_extensions(original_template_dict, parameter_values, enabled=True)
        except InvalidSamDocumentException as e:
            raise PackageFailedError(template_file=self.template_file, ex=str(e)) from e

        template = Template(
            template_path,
            os.getcwd(),
            self.uploaders,
            self.code_signer,
            normalize_template=True,
            normalize_parameters=True,
            template_dict=copy.deepcopy(result.expanded_template),
            parameter_values=parameter_values,
            language_extensions_enabled=True,
        )
        exported_template = template.export()

        if not result.had_language_extensions:
            return exported_template

        LOG.debug("Template uses language extensions, preserving Fn::ForEach structure")
        output_template = merge_language_extensions_s3_uris(
            result.original_template, exported_template, result.dynamic_artifact_properties
        )
        if result.dynamic_artifact_properties:
            LOG.debug(
                "Generating Mappings for %d dynamic artifact properties",
                len(result.dynamic_artifact_properties),
            )
            output_template = generate_and_apply_artifact_mappings(
                output_template,
                result.dynamic_artifact_properties,
                exported_template.get("Resources", {}),
                template_dir,
            )
        return output_template

    @staticmethod
    def _warn_preview_runtime(stacks: List[Stack]) -> None:
        for stack in stacks:
            for _, resource_dict in stack.resources.items():
                if resource_dict.get("Type") not in [AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION]:
                    continue
                if resource_dict.get("Properties", {}).get("Runtime", "") in PREVIEW_RUNTIMES:
                    click.secho(
                        "Warning: This stack contains one or more Lambda functions using a runtime which is not "
                        "yet generally available. This runtime should not be used for production applications. "
                        "For more information on supported runtimes, see "
                        "https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html.",
                        fg="yellow",
                    )
                return

    @staticmethod
    def write_output(output_file_name: Optional[str], data: str) -> None:
        if output_file_name is None:
            click.echo(data)
            return

        with open(output_file_name, "w") as fp:
            fp.write(data)

    @property
    def language_extensions_enabled(self) -> bool:
        return self._language_extensions_enabled
