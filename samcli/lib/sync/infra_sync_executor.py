"""
InfraSyncExecutor class which runs build, package and deploy contexts
"""

import copy
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set, cast
from uuid import uuid4

from boto3 import Session
from botocore.exceptions import ClientError

from samcli.commands._utils.template import get_template_data
from samcli.commands.build.build_context import BuildContext
from samcli.commands.deploy.deploy_context import DeployContext
from samcli.commands.package.package_context import PackageContext
from samcli.lib.providers.provider import ResourceIdentifier
from samcli.lib.providers.sam_stack_provider import is_local_path
from samcli.lib.telemetry.event import EventTracker
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
    CODE_SYNCABLE_RESOURCES,
    SYNCABLE_STACK_RESOURCES,
)
from samcli.yamlhelper import yaml_parse

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.sync.sync_context import SyncContext

LOG = logging.getLogger(__name__)

GENERAL_REMOVAL_MAP = {
    AWS_SERVERLESS_FUNCTION: ["CodeUri", "ImageUri"],
    AWS_SERVERLESS_LAYERVERSION: ["ContentUri"],
    AWS_LAMBDA_LAYERVERSION: ["Content"],
    AWS_SERVERLESS_API: ["DefinitionUri"],
    AWS_APIGATEWAY_RESTAPI: ["BodyS3Location"],
    AWS_SERVERLESS_HTTPAPI: ["DefinitionUri"],
    AWS_APIGATEWAY_V2_API: ["BodyS3Location"],
    AWS_SERVERLESS_STATEMACHINE: ["DefinitionUri"],
    AWS_STEPFUNCTIONS_STATEMACHINE: ["DefinitionS3Location"],
    AWS_SERVERLESS_APPLICATION: ["Location"],
    AWS_CLOUDFORMATION_STACK: ["TemplateURL"],
}

LAMBDA_FUNCTION_REMOVAL_MAP = {
    AWS_LAMBDA_FUNCTION: {"Code": ["ImageUri", "S3Bucket", "S3Key", "S3ObjectVersion"]},
}

AUTO_INFRA_SYNC_DAYS = 7
SYNC_FLOW_THRESHOLD = 50


class InfraSyncResult:
    """Data class for storing infra sync result"""

    _infra_sync_executed: bool
    _code_sync_resources: Set[ResourceIdentifier]

    def __init__(self, executed: bool, code_sync_resources: Set[ResourceIdentifier] = set()) -> None:
        """
        Constructor

        Parameters
        ----------
        Executed: bool
            Infra sync execution happened or not
        code_sync_resources: Set[ResourceIdentifier]
            Resources that needs a code sync
        """
        self._infra_sync_executed = executed
        self._code_sync_resources = code_sync_resources

    @property
    def infra_sync_executed(self) -> bool:
        """Returns a boolean indicating whether infra sync executed"""
        return self._infra_sync_executed

    @property
    def code_sync_resources(self) -> Set[ResourceIdentifier]:
        """Returns a set of resource identifiers that need a code sync"""
        return self._code_sync_resources


class InfraSyncExecutor:
    """
    Executor for infra sync that contains skip logic when template is not changed
    """

    _build_context: BuildContext
    _package_context: PackageContext
    _deploy_context: DeployContext
    _code_sync_resources: Set[ResourceIdentifier]

    def __init__(
        self,
        build_context: BuildContext,
        package_context: PackageContext,
        deploy_context: DeployContext,
        sync_context: "SyncContext",
    ):
        """Constructs the sync for infra executor.

        Parameters
        ----------
        build_context : BuildContext
        package_context : PackageContext
        deploy_context : DeployContext
        sync_context : SyncContext
        """
        self._build_context = build_context
        self._package_context = package_context
        self._deploy_context = deploy_context
        self._sync_context = sync_context

        self._code_sync_resources = set()

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

    def execute_infra_sync(self, first_sync: bool = False) -> InfraSyncResult:
        """
        Compares the local template with the deployed one, executes infra sync if different

        Parameters
        ----------
        first_sync: bool
            A flag that signals the inital run, only true when it's the first time running infra sync

        Returns
        -------
        InfraSyncResult
            Returns information containing whether infra sync executed plus resources to do code sync on
        """
        self._build_context.set_up()
        self._build_context.run()
        self._package_context.run()

        last_infra_sync_time = self._sync_context.get_latest_infra_sync_time()
        days_since_last_infra_sync = 0
        if last_infra_sync_time:
            current_time = datetime.utcnow()
            days_since_last_infra_sync = (current_time - last_infra_sync_time).days

        # Will not combine the comparisons in order to save operation cost
        thread_id = uuid4()
        if self._sync_context.skip_deploy_sync and first_sync and (days_since_last_infra_sync <= AUTO_INFRA_SYNC_DAYS):
            EventTracker.track_event("SyncFlowStart", "SkipInfraSyncExecute", thread_id=thread_id)
            try:
                if self._auto_skip_infra_sync(
                    self._package_context.output_template_file,
                    self._package_context.template_file,
                    self._deploy_context.stack_name,
                    self._build_context._parameter_overrides or {},
                ):
                    # We have a threshold on number of sync flows we initiate
                    # If higher than the threshold, we perform infra sync to improve performance
                    if len(self.code_sync_resources) < SYNC_FLOW_THRESHOLD:
                        LOG.info("Template haven't been changed since last deployment, skipping infra sync...")
                        EventTracker.track_event("SyncFlowEnd", "SkipInfraSyncExecute", thread_id=thread_id)
                        return InfraSyncResult(False, self.code_sync_resources)
                    else:
                        LOG.info(
                            "The number of resources that needs an update exceeds %s, \
an infra sync will be executed for an CloudFormation deployment to improve performance",
                            SYNC_FLOW_THRESHOLD,
                        )
            except Exception:
                LOG.debug(
                    "Could not skip infra sync by comparing to a previously deployed template, starting infra sync"
                )

        EventTracker.track_event("SyncFlowStart", "InfraSyncExecute", thread_id=thread_id)
        if days_since_last_infra_sync > AUTO_INFRA_SYNC_DAYS:
            LOG.info(
                "Infrastructure Sync hasn't been run in the last %s days, sam sync will be queuing up the stack"
                " deployment to minimize the drift in CloudFormation.",
                AUTO_INFRA_SYNC_DAYS,
            )
        self._deploy_context.run()
        EventTracker.track_event("SyncFlowEnd", "InfraSyncExecute", thread_id=thread_id)

        # Update latest infra sync time in sync state
        self._sync_context.update_infra_sync_time()

        return InfraSyncResult(True)

    def _auto_skip_infra_sync(
        self,
        packaged_template_path: str,
        built_template_path: str,
        stack_name: str,
        parameter_overrides: Optional[Dict[str, str]] = None,
        nested_prefix: Optional[str] = None,
    ) -> bool:
        """
        Recursively compares two templates, including the nested templates referenced inside

        Parameters
        ----------
        packaged_template_path : str
            The template location of the current template packaged
        built_template_path : str
            The template location of the current template built
        stack_name : str
            The CloudFormation stack name that the template is deployed to
        nested_prefix: Optional[str]
            The nested stack stack name tree for child stack resources
        parameter_overrides: Optional[Dict[str,str]]
            Parameter overrides passed into sam sync in the form of { KEY1 : VALUE1, KEY2 : VALUE2 }

        Returns
        -------
        bool
            Returns True if no template changes from last deployment
            Returns False if there are template differences
        """
        parameter_overrides = parameter_overrides or {}

        current_template = self.get_template(packaged_template_path)
        current_built_template = self.get_template(built_template_path)

        if not current_template or not current_built_template:
            LOG.debug("Cannot obtain a working current template for template path")
            return False

        try:
            last_deployed_template_str = self._cfn_client.get_template(
                StackName=stack_name, TemplateStage="Original"
            ).get("TemplateBody", "")
        except ClientError as ex:
            LOG.debug("Stack with name %s does not exist on CloudFormation", stack_name, exc_info=ex)
            return False

        last_deployed_template_dict = yaml_parse(last_deployed_template_str)

        sanitized_current_template = copy.deepcopy(current_template)
        sanitized_last_template = copy.deepcopy(last_deployed_template_dict)

        sanitized_resources = self._sanitize_template(
            sanitized_current_template, built_template_dict=current_built_template
        )
        self._sanitize_template(sanitized_last_template, linked_resources=sanitized_resources)

        if sanitized_last_template != sanitized_current_template:
            LOG.debug("The current template is different from the last deployed version, we will not skip infra sync")
            return False

        if not self._param_overrides_subset_of_stack_params(stack_name, parameter_overrides):
            return False

        # The recursive template check for Nested stacks
        for resource_logical_id in current_template.get("Resources", {}):
            resource_dict = current_template.get("Resources", {}).get(resource_logical_id, {})
            resource_type = resource_dict.get("Type")

            if resource_type in CODE_SYNCABLE_RESOURCES:
                last_resource_dict = last_deployed_template_dict.get("Resources", {}).get(resource_logical_id, {})
                resource_resolved_id = nested_prefix + resource_logical_id if nested_prefix else resource_logical_id

                if resource_type == AWS_LAMBDA_FUNCTION:
                    if not resource_dict.get("Properties", {}).get("Code", None) == last_resource_dict.get(
                        "Properties", {}
                    ).get("Code", None):
                        self._code_sync_resources.add(ResourceIdentifier(resource_resolved_id))
                else:
                    for field in GENERAL_REMOVAL_MAP.get(resource_type, []):
                        if not resource_dict.get("Properties", {}).get(field, None) == last_resource_dict.get(
                            "Properties", {}
                        ).get(field, None):
                            self._code_sync_resources.add(ResourceIdentifier(resource_resolved_id))

            if resource_type in SYNCABLE_STACK_RESOURCES:
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
                template_location = resource_dict.get("Properties", {}).get(template_field)

                # For AWS::Serverless::Application, location can be a ApplicationLocationObject dict containing SAR ID
                if isinstance(template_location, dict):
                    continue
                # For other scenarios, template location will be a string (local or s3 URL)
                nested_template_location = (
                    current_built_template.get("Resources", {})
                    .get(resource_logical_id, {})
                    .get("Properties", {})
                    .get(template_field)
                )
                if is_local_path(nested_template_location):
                    nested_template_location = str(Path(built_template_path).parent.joinpath(nested_template_location))
                if not self._auto_skip_infra_sync(
                    resource_dict.get("Properties", {}).get(template_field),
                    nested_template_location,
                    stack_resource_detail.get("StackResourceDetail", {}).get("PhysicalResourceId", ""),
                    parameter_overrides={},  # Do not pass the same parameter overrides to the nested stack
                    nested_prefix=(
                        nested_prefix + resource_logical_id + "/" if nested_prefix else resource_logical_id + "/"
                    ),
                ):
                    return False

        LOG.debug("There are no changes from the previously deployed template for %s", packaged_template_path)
        return True

    def _sanitize_template(
        self,
        template_dict: Dict,
        linked_resources: Optional[Set[str]] = None,
        built_template_dict: Optional[Dict] = None,
    ) -> Set[str]:
        """
        Fields skipped during template comparison because sync --code can handle the difference:
        * CodeUri or ImageUri property of AWS::Serverless::Function
        * ImageUri, S3Bucket, S3Key, S3ObjectVersion fields in Code property of AWS::Lambda::Function
        * ContentUri property of AWS::Serverless::LayerVersion
        * Content property of AWS::Lambda::LayerVersion
        * DefinitionUri property of AWS::Serverless::Api
        * BodyS3Location property of AWS::ApiGateway::RestApi
        * DefinitionUri property of AWS::Serverless::HttpApi
        * BodyS3Location property of AWS::ApiGatewayV2::Api
        * DefinitionUri property of AWS::Serverless::StateMachine
        * DefinitionS3Location property of AWS::StepFunctions::StateMachine

        Fields skipped during template comparison because we have recursive compare logic for nested stack:
        * Location property of AWS::Serverless::Application
        * TemplateURL property of AWS::CloudFormation::Stack

        Fields skipped during template comparison because it's a metadata generated by SAM
        * SamResourceId in Metadata property of all resources

        Parameters
        ----------
        template_dict: Dict
            The unprocessed template dictionary
        linked_resources: List[str]
            The corresponding resources in the other template that got processed
        built_template_dict: Optional[Dict]
            The built template dict that the paths didn't get replaced with packaged links yet

        Returns
        -------
        Set[str]
            The list of resource IDs that got changed during sanitization
        """
        linked_resources = linked_resources or set()

        resources = template_dict.get("Resources", {})
        processed_resources: Set[str] = set()
        built_resource_dict = None

        for resource_logical_id in resources:
            resource_dict = resources.get(resource_logical_id, {})

            # Built resource dict helps with determining if a field is a local path
            if built_template_dict:
                built_resource_dict = built_template_dict.get("Resources", {}).get(resource_logical_id, {})

            resource_type = resource_dict.get("Type")

            if resource_type in CODE_SYNCABLE_RESOURCES or resource_type in SYNCABLE_STACK_RESOURCES:
                processed_resource = self._remove_resource_field(
                    resource_logical_id,
                    resource_type,
                    resource_dict,
                    linked_resources,
                    built_resource_dict if built_template_dict else None,
                )

                if processed_resource:
                    LOG.debug("Sanitized %s resource %s", resource_type, resource_logical_id)
                    processed_resources.add(processed_resource)

            # Remove SamResourceId metadata since this metadata does not affect any cloud behaviour
            resource_dict.get("Metadata", {}).pop("SamResourceId", None)
            if not resource_dict.get("Metadata"):
                resource_dict.pop("Metadata", None)
            LOG.debug("Sanitizing the Metadata for resource %s", resource_logical_id)

        return processed_resources

    def _remove_resource_field(
        self,
        resource_logical_id: str,
        resource_type: str,
        resource_dict: Dict,
        linked_resources: Optional[Set[str]] = None,
        built_resource_dict: Optional[Dict] = None,
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
        linked_resources: Optional[Set[str]]
            The corresponding resources in the other template that got processed
        built_resource_dict: Optional[Dict]
            Only passed in for current template sanitization to determine if local

        Returns
        -------
        Optional[str]
            The processed resource ID
        """
        linked_resources = linked_resources or set()
        processed_logical_id = None

        if resource_type == AWS_LAMBDA_FUNCTION:
            for field in LAMBDA_FUNCTION_REMOVAL_MAP.get(resource_type, {}).get("Code", []):
                # We sanitize only if the provided resource is local
                # Lambda function's Code property accepts dictionary values
                if (
                    built_resource_dict
                    and isinstance(built_resource_dict.get("Properties", {}).get("Code"), dict)
                    and is_local_path(built_resource_dict.get("Properties", {}).get("Code", {}).get(field, None))
                ) or resource_logical_id in linked_resources:
                    resource_dict.get("Properties", {}).get("Code", {}).pop(field, None)
                    processed_logical_id = resource_logical_id
                # SAM templates also accepts local paths for AWS::Lambda::Function's Code property
                # Which will be transformed into a dict containing S3Bucket and S3Key after packaging
                if (
                    built_resource_dict
                    and isinstance(built_resource_dict.get("Properties", {}).get("Code"), str)
                    and is_local_path(built_resource_dict.get("Properties", {}).get("Code"))
                ):
                    resource_dict.get("Properties", {}).get("Code", {}).pop("S3Bucket", None)
                    resource_dict.get("Properties", {}).get("Code", {}).pop("S3Key", None)
                    processed_logical_id = resource_logical_id
        else:
            for field in GENERAL_REMOVAL_MAP.get(resource_type, []):
                if resource_type in SYNCABLE_STACK_RESOURCES:
                    if not isinstance(resource_dict.get("Properties", {}).get(field, None), dict):
                        resource_dict.get("Properties", {}).pop(field, None)
                        processed_logical_id = resource_logical_id
                elif (
                    built_resource_dict and is_local_path(built_resource_dict.get("Properties", {}).get(field, None))
                ) or resource_logical_id in linked_resources:
                    resource_dict.get("Properties", {}).pop(field, None)
                    processed_logical_id = resource_logical_id

        return processed_logical_id

    def get_template(self, template_path: str) -> Optional[Dict]:
        """
        Returns the template dict based on local or remote read logic

        Parameters
        ----------
        template_path: str
            The location of the template

        Returns
        -------
        Dict
            The parsed template dict
        """
        template = None
        # If the customer template uses a nested stack with location/template URL in S3
        if template_path.startswith("https://"):
            template = self._get_remote_template_data(template_path)

        # If the template location is local
        else:
            template = get_template_data(template_path)

        return template

    def _param_overrides_subset_of_stack_params(self, stack_name: str, param_overrides: Dict[str, str]) -> bool:
        """
        Returns whether or not the supplied parameter overrides are a subset of the current stack parameters

        Parameters
        ----------
        stack_name: str

        param_overrides: Dict[str, str]
            Parameter overrides supplied by the sam sync command, taking the following format
            e.g. {'Foo1': 'Bar1', 'Foo2': 'Bar2'}

        """

        # Current stack parameters returned from describe_stacks, taking the following format
        # e.g [{'ParameterKey': 'Foo1', 'ParameterValue': 'Bar1'}, {'ParameterKey': 'Foo2', 'ParameterValue': 'Bar2'}]

        try:
            current_stack_params = self._get_stack_parameters(stack_name)
        except ClientError as ex:
            LOG.debug("Unable to fetch stack Parameters from stack with name %s", stack_name, exc_info=ex)
            return False

        # We can flatten the current stack parameters into the same format as the parameter overrides
        # This allows us to check if the parameter overrides are a direct subset of the current stack parameters

        flat_current_stack_parameters = {}
        for param in current_stack_params:
            flat_current_stack_parameters[param["ParameterKey"]] = param["ParameterValue"]

        # Check for parameter overrides being a subset of the current stack parameters
        if not (param_overrides.items() <= flat_current_stack_parameters.items()):
            LOG.debug("Detected changes between Parameter overrides and the current stack parameters.")
            return False

        return True

    def _get_stack_parameters(self, stack_name: str) -> List[Dict[str, str]]:
        """
        Returns the stack parameters for a given stack

        Parameters
        ----------
        stack_name: str
            The name of the stack

        Returns
        -------
            List of Dicts in the form { 'ParameterKey': Foo, 'ParameterValue': Bar }

        """
        stacks = self._cfn_client.describe_stacks(StackName=stack_name).get("Stacks")

        if len(stacks) < 1:
            LOG.info(
                "Failed to pull stack details for stack with name %s, it may not yet be finished deploying.", stack_name
            )
            return []

        return cast(
            List[Dict[str, str]],
            stacks[0].get("Parameters", []),
        )

    def _get_remote_template_data(self, template_path: str) -> Optional[Dict]:
        """
        Get template dict from remote location

        Parameters
        ----------
        template_path: str
            The s3 location of the template

        Returns
        -------
        Dict
            The parsed template dict from s3
        """
        template = None

        parsed_s3_location = re.search(r"https:\/\/[^/]*\/([^/]*)\/(.*)", template_path)
        if parsed_s3_location:
            s3_bucket = parsed_s3_location.group(1)
            s3_key = parsed_s3_location.group(2)
            try:
                s3_object = self._s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
            except ClientError as ex:
                LOG.debug("The provided template location %s can not be found", template_path, exc_info=ex)
            else:
                streaming_body = s3_object.get("Body")
                if streaming_body:
                    template = yaml_parse(streaming_body.read().decode("utf-8"))

        return template

    @property
    def code_sync_resources(self) -> Set[ResourceIdentifier]:
        """Returns the list of resources that should trigger code sync"""
        return self._code_sync_resources
