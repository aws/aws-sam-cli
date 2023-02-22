"""
InfraSyncExecutor class which runs build, package and deploy contexts
"""
import logging
import re
from typing import Dict, Optional, Set

from boto3 import Session
from botocore.exceptions import ClientError

from samcli.commands._utils.template import get_template_data
from samcli.commands.build.build_context import BuildContext
from samcli.commands.deploy.deploy_context import DeployContext
from samcli.commands.package.package_context import PackageContext
from samcli.lib.providers.sam_stack_provider import is_local_path
from samcli.lib.utils.boto_utils import get_boto_client_provider_from_session_with_config
from samcli.lib.utils.resources import (
    AWS_APIGATEWAY_RESTAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_CLOUDFORMATION_STACK,
    AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_API,
    AWS_SERVERLESS_APPLICATION,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_HTTPAPI,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_SERVERLESS_STATEMACHINE,
    AWS_STEPFUNCTIONS_STATEMACHINE,
    SYNCABLE_RESOURCES,
)
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)

GENERAL_REMOVAL_MAP = {
    AWS_SERVERLESS_FUNCTION: ["CodeUri", "ImageUri"],
    AWS_SERVERLESS_LAYERVERSION: ["ContentUri"],
    AWS_LAMBDA_LAYERVERSION: ["Content"],
    AWS_SERVERLESS_API: ["DefinitionBody"],
    AWS_APIGATEWAY_RESTAPI: ["BodyS3Location"],
    AWS_SERVERLESS_HTTPAPI: ["DefinitionUri"],
    AWS_APIGATEWAY_V2_API: ["BodyS3Location"],
    AWS_SERVERLESS_STATEMACHINE: ["DefinitionUri"],
    AWS_STEPFUNCTIONS_STATEMACHINE: ["DefinitionS3Location"],
}

LAMBDA_FUNCTION_REMOVAL_MAP = {
    AWS_LAMBDA_FUNCTION: {"Code": ["ImageUri", "S3Bucket", "S3Key", "S3ObjectVersion"]},
}


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
        self._cfn_client = self._boto_client("cloudformation", session)
        self._s3_client = self._boto_client("s3", session)

    def _boto_client(self, client_name: str, session: Session):
        """
        Creates boto client

        Parameters
        ----------
        client_name: str
            The name of the client
        session: boto3.Session
            The session created using customer config

        Returns
        -------
        Service client instance
        """
        return get_boto_client_provider_from_session_with_config(session)(client_name)

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
        current_template = None
        # If the customer template uses a nested stack with location/template URL in S3
        if local_template_path.startswith("https://"):
            parsed_s3_location = re.search(r"https:\/\/[^/]*\/([^/]*)\/(.*)", local_template_path)
            if parsed_s3_location:
                s3_bucket = parsed_s3_location.group(1)
                s3_key = parsed_s3_location.group(2)
                try:
                    s3_object = self._s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
                except ClientError as ex:
                    LOG.debug("The provided template location %s can not be found", local_template_path, exc_info=ex)
                    return False

                streaming_body = s3_object.get("Body")
                if streaming_body:
                    current_template = yaml_parse(streaming_body.read().decode("utf-8"))

        # If the template location is local
        else:
            current_template = get_template_data(local_template_path)

        if not current_template:
            LOG.debug("Cannot obtain a working current template for template path %s", local_template_path)
            return False

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
            LOG.debug("The current template is different from the last deployed version, we will not skip infra sync")
            return False

        # The recursive template check for Nested stacks
        for resource_logical_id in current_template.get("Resources", {}):
            resource_dict = current_template.get("Resources", {}).get(resource_logical_id, {})
            resource_type = resource_dict.get("Type")
            if resource_type == AWS_CLOUDFORMATION_STACK or resource_type == AWS_SERVERLESS_APPLICATION:
                try:
                    stack_resource_detail = self._cfn_client.describe_stack_resource(
                        StackName=stack_name, LogicalResourceId=resource_logical_id
                    )
                except ClientError as ex:
                    LOG.debug(
                        "Cannot get resource detail with name %s on CloudFormation", resource_logical_id, exc_info=ex
                    )
                    return False

                # If the nested stack is of type AWS::CloudFormation::Stack,
                # The template location will be under TemplateURL property
                # If the nested stack is of type AWS::Serverless::Application,
                # the template location will be under Location property
                template_field = "TemplateURL" if resource_type == AWS_CLOUDFORMATION_STACK else "Location"
                if not self._compare_templates(
                    resource_dict.get("Properties", {}).get(template_field),
                    stack_resource_detail.get("StackResourceDetail", {}).get("PhysicalResourceId", ""),
                ):
                    return False

        LOG.debug("There are no changes from the previously deployed template for %s", local_template_path)
        return True

    def _remove_unnecessary_fields(self, template_dict: Dict, linked_resources: Set[str] = set()) -> Set[str]:
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
        template_dict: Dict
            The unprocessed template dictionary
        linked_resources: List[str]
            The corresponding resources in the other template that got processed

        Returns
        -------
        List[str]
            The list of resource IDs that got changed during sanitization
        """

        resources = template_dict.get("Resources", {})
        processed_resources: Set[str] = set()

        for resource_logical_id in resources:
            resource_dict = resources.get(resource_logical_id, {})
            resource_type = resource_dict.get("Type")

            if resource_type in SYNCABLE_RESOURCES:
                processed_resource = self._remove_resource_field(
                    resource_logical_id,
                    resource_type,
                    resource_dict,
                    linked_resources,
                )

                if processed_resource:
                    LOG.debug("Sanitized %s resource %s", resource_type, resource_logical_id)
                    processed_resources.add(processed_resource)

            # Remove SamResourceId metadata since this metadata does not affect any cloud behaviour
            resource_dict.get("Metadata", {}).pop("SamResourceId", None)
            if not resource_dict.get("Metadata"):
                resource_dict.pop("Metadata", None)
            LOG.debug("Sanitizing the Metadata for resource %s", resource_logical_id)

        return sorted(processed_resources)

    def _remove_resource_field(
        self,
        resource_logical_id: str,
        resource_type: str,
        resource_dict: Dict,
        linked_resources: Set[str] = set(),
    ) -> Optional[str]:
        """
        Helper method to process resource dict

        Parameters
        ----------
        resource_logical_id: str
            Logical ID of the resource
        resource_type: str
            Resource type
        resource_dict: Dict
            The resource level dict containing Properties field
        processed_resources: set
            The set of already processed resource IDs
        linked_resources: Set[str]
            The corresponding resources in the other template that got processed

        Returns
        -------
        Optional[str]
            The processed resource ID
        """
        processed_logical_id = None

        if resource_type == AWS_LAMBDA_FUNCTION:
            for field in LAMBDA_FUNCTION_REMOVAL_MAP.get(resource_type, {}).get("Code", []):  # type: ignore
                if (
                    is_local_path(resource_dict.get("Properties", {}).get("Code", {}).get(field, None))
                    or resource_logical_id in linked_resources
                ):
                    resource_dict.get("Properties", {}).get("Code", {}).pop(field, None)
                    processed_logical_id = resource_logical_id
        else:
            for field in GENERAL_REMOVAL_MAP.get(resource_type, []):
                if (
                    is_local_path(resource_dict.get("Properties", {}).get(field, None))
                    or resource_logical_id in linked_resources
                ):
                    resource_dict.get("Properties", {}).pop(field, None)
                    processed_logical_id = resource_logical_id

        return processed_logical_id
