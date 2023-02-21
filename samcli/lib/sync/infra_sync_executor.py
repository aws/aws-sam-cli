"""
InfraSyncExecutor class which runs build, package and deploy contexts
"""
import logging
import re

from typing import Dict, List, Optional

from boto3 import Session
from botocore.exceptions import ClientError

from samcli.commands._utils.template import get_template_data
from samcli.commands.build.build_context import BuildContext
from samcli.commands.deploy.deploy_context import DeployContext
from samcli.commands.package.package_context import PackageContext
from samcli.lib.providers.sam_stack_provider import is_local_path
from samcli.lib.utils.resources import (
    AWS_SERVERLESS_FUNCTION,
    AWS_LAMBDA_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_API,
    AWS_APIGATEWAY_RESTAPI,
    AWS_SERVERLESS_HTTPAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_SERVERLESS_STATEMACHINE,
    AWS_STEPFUNCTIONS_STATEMACHINE,
    SYNCABLE_RESOURCES,
)
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)


class InfraSyncExecutor:
    """
    Executor for infra sync that contains skip logic when template is not changed
    """

    _build_context: BuildContext
    _package_context: PackageContext
    _deploy_context: DeployContext

    def __init__(self, build_context: BuildContext, package_context: PackageContext, deploy_context: DeployContext):
        """Constructs the sync for infra executor.

        Parameters
        ----------
        build_context : BuildContext
            BuildContext
        package_context : PackageContext
            PackageContext
        deploy_context : DeployContext
            DeployContext
        """
        self._build_context = build_context
        self._package_context = package_context
        self._deploy_context = deploy_context

        session = Session(profile_name=self._deploy_context.profile, region_name=self._deploy_context.region)
        self._cfn_client = session.client("cloudformation")
        self._s3_client = session.client("s3")

    def _compare_templates(self, local_template_path: str, stack_name: str) -> bool:
        """
        Recursively conpares two templates, including the nested templates referenced inside

        Parameters
        ----------
        local_template_path : str
            The local template location
        stack_name : str
            The CloudFormation stack name that the template is deployed to

        Returns
        -------
        bool
            Returns True if two templates are identical
            Returns False if two templates are different
        """
        try:
            # If the customer template uses a nested stack with location/template URL in S3
            if local_template_path.startswith("https://"):
                parsed_s3_location = re.search(r"https:\/\/[^/]*\/([^/]*)\/(.*)", local_template_path)
                s3_bucket = parsed_s3_location.group(1)
                s3_key = parsed_s3_location.group(2)
                s3_object = self._s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
                current_template = yaml_parse(s3_object.get("Body").read().decode("utf-8"))
            # If the template location is local
            else:
                current_template = get_template_data(local_template_path)

            try:
                last_deployed_template_str = self._cfn_client.get_template(
                    StackName=stack_name, TemplateStage="Original"
                ).get("TemplateBody", "")
            except ClientError as ex:
                LOG.debug("Stack with name %s does not exist on CloudFormation", stack_name, exc_info=ex)
                return False

            last_deployed_template_dict = yaml_parse(last_deployed_template_str)

            sanitized_resources = self._remove_unnecessary_fields(current_template)
            self._remove_unnecessary_fields(last_deployed_template_dict, sanitized_resources)

            if last_deployed_template_dict != current_template:
                return False

            # The recursive template check for Nested stacks
            for resource_logical_id in current_template.get("Resources", {}):
                resource_dict = current_template.get("Resources", {}).get(resource_logical_id, {})
                resource_type = resource_dict.get("Type")
                if resource_type == "AWS::CloudFormation::Stack" or resource_type == "AWS::Serverless::Application":
                    stack_resource_detail = self._cfn_client.describe_stack_resource(
                        StackName=stack_name, LogicalResourceId=resource_logical_id
                    )

                    # If the nested stack is of type AWS::CloudFormation::Stack,
                    # The template location will be under TemplateURL property
                    # If the nested stack is of type AWS::Serverless::Application,
                    # the template location will be under Location property
                    template_field = "TemplateURL" if resource_type == "AWS::CloudFormation::Stack" else "Location"
                    if not self._compare_templates(
                        resource_dict.get("Properties", {}).get(template_field),
                        stack_resource_detail.get("StackResourceDetail", {}).get("PhysicalResourceId"),
                    ):
                        return False
        except Exception:
            LOG.debug("Template comparison with the cloud template failed, not skipping infra sync")
            return False

        return True

    def _remove_unnecessary_fields(
        self, template_dict: Dict, sanitized_resources: Optional[List[str]] = None
    ) -> List[str]:
        """
        Fields skipped during template comparison because sync --code can handle the difference:
        * CodeUri or ImageUri property of AWS::Serverless::Function
        * ImageUri, S3Bucket, S3Key, S3ObjectVersion fields in Code property of AWS::Lambda::Function
        * ContentUri property of AWS::Serverless::LayerVersion
        * Content property of AWS::Lambda::LayerVersion
        * DefinitionBody property of AWS::Serverless::Api
        * BodyS3Location property of AWS::ApiGateway::RestApi
        * DefinitionUri property of AWS::Serverless::HttpApi
        * BodyS3Location property of AWS::ApiGatewayV2::Api
        * DefinitionUri property of AWS::Serverless::StateMachine
        * DefinitionS3Location property of AWS::StepFunctions::StateMachine
        * SamResourceId in Metadata property of all resources

        Parameters
        ----------
        template_dict : Dict
            The unprocessed template dictionary
        sanitized_resources: Optional[List[str]]
            The corresponding resources in the other template that got processed

        Returns
        -------
        List[str]
            The list of resource IDs that got changed during sanitization
        """

        resources = template_dict.get("Resources", {})
        processed_resources = set()

        for resource_logical_id in resources:
            resource_dict = resources.get(resource_logical_id, {})
            resource_type = resource_dict.get("Type")

            if resource_type in SYNCABLE_RESOURCES:

                # CodeUri or ImageUri property of AWS::Serverless::Function
                if resource_type == AWS_SERVERLESS_FUNCTION:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("CodeUri", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("CodeUri", None)
                        processed_resources.add(resource_logical_id)
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("ImageUri", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("ImageUri", None)
                        processed_resources.add(resource_logical_id)

                # ImageUri, S3Bucket, S3Key, S3ObjectVersion fields in Code property of AWS::Lambda::Function
                if resource_type == AWS_LAMBDA_FUNCTION:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("Code", {}).get("ImageUri", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).get("Code", {}).pop("ImageUri", None)
                        processed_resources.add(resource_logical_id)
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("Code", {}).get("S3Bucket", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).get("Code", {}).pop("S3Bucket", None)
                        processed_resources.add(resource_logical_id)
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("Code", {}).get("S3Key", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).get("Code", {}).pop("S3Key", None)
                        processed_resources.add(resource_logical_id)
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("Code", {}).get("S3ObjectVersion", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).get("Code", {}).pop("S3ObjectVersion", None)
                        processed_resources.add(resource_logical_id)

                # ContentUri property of AWS::Serverless::LayerVersion
                if resource_type == AWS_SERVERLESS_LAYERVERSION:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("ContentUri", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("ContentUri", None)
                        processed_resources.add(resource_logical_id)

                # Content property of AWS::Lambda::LayerVersion
                if resource_type == AWS_LAMBDA_LAYERVERSION:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("Content", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("Content", None)
                        processed_resources.add(resource_logical_id)

                # DefinitionBody property of AWS::Serverless::Api
                if resource_type == AWS_SERVERLESS_API:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("DefinitionBody", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("DefinitionBody", None)
                        processed_resources.add(resource_logical_id)

                # BodyS3Location property of AWS::ApiGateway::RestApi
                if resource_type == AWS_APIGATEWAY_RESTAPI:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("BodyS3Location", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("BodyS3Location", None)
                        processed_resources.add(resource_logical_id)

                # DefinitionUri property of AWS::Serverless::HttpApi
                if resource_type == AWS_SERVERLESS_HTTPAPI:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("DefinitionUri", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("DefinitionUri", None)
                        processed_resources.add(resource_logical_id)

                # BodyS3Location property of AWS::ApiGatewayV2::Api
                if resource_type == AWS_APIGATEWAY_V2_API:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("BodyS3Location", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("BodyS3Location", None)
                        processed_resources.add(resource_logical_id)

                # DefinitionUri property of AWS::Serverless::StateMachine
                if resource_type == AWS_SERVERLESS_STATEMACHINE:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("DefinitionUri", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("DefinitionUri", None)
                        processed_resources.add(resource_logical_id)

                # DefinitionS3Location property of AWS::StepFunctions::StateMachine
                if resource_type == AWS_STEPFUNCTIONS_STATEMACHINE:
                    if (
                        is_local_path(resource_dict.get("Properties", {}).get("DefinitionS3Location", None))
                        or resource_logical_id in sanitized_resources
                    ):
                        resource_dict.get("Properties", {}).pop("DefinitionS3Location", None)
                        processed_resources.add(resource_logical_id)

                LOG.debug(f"Sanitizing the {resource_type} resource {resource_logical_id}")

            # Remove SamResourceId metadata since this metadata does not affect any cloud behaviour
            resource_dict.get("Metadata", {}).pop("SamResourceId", None)
            if not resource_dict.get("Metadata"):
                resource_dict.pop("Metadata", None)
            LOG.debug(f"Sanitizing the Metadata for resource {resource_logical_id}")

        return sorted(list(processed_resources))
