"""
The producer for the 'sam list resources' command
"""
import dataclasses
import logging
from typing import Any, Dict

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from samtranslator.translator.arn_generator import NoRegionFound
from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader

from samcli.commands._utils.template import get_template_data
from samcli.commands.exceptions import UserException
from samcli.commands.list.exceptions import (
    SamListLocalResourcesNotFoundError,
    SamListUnknownBotoCoreError,
    SamListUnknownClientError,
    StackDoesNotExistInRegionError,
)
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.list.list_interfaces import Producer
from samcli.lib.list.resources.resources_def import ResourcesDef
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.translate.sam_template_validator import SamTemplateValidator
from samcli.lib.utils.boto_utils import get_client_error_code
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)

ROOT_STACK = 0


class ResourceMappingProducer(Producer):
    def __init__(
        self,
        stack_name,
        region,
        profile,
        template_file,
        cloudformation_client,
        iam_client,
        mapper,
        consumer,
        parameter_overrides=None,
    ):
        self.parameter_overrides = parameter_overrides
        self.stack_name = stack_name
        self.region = region
        self.profile = profile
        self.template_file = template_file
        self.cloudformation_client = cloudformation_client
        self.iam_client = iam_client
        self.mapper = mapper
        self.consumer = consumer

    def get_resources_info(self):
        """
        Returns the stack resources information for the stack and raises exceptions accordingly

        Returns
        -------
            A dictionary containing information about the stack's resources
        """

        try:
            all_resources = []
            cfn_paginator = self.cloudformation_client.get_paginator("list_stack_resources")
            for response in cfn_paginator.paginate(StackName=self.stack_name):
                if "StackResourceSummaries" not in response:
                    continue

                all_resources.extend(response.get("StackResourceSummaries", []))

            return {"StackResources": all_resources}
        except ClientError as e:
            if get_client_error_code(e) == "ValidationError":
                LOG.debug("Stack with id %s does not exist", self.stack_name)
                raise StackDoesNotExistInRegionError(stack_name=self.stack_name, region=self.region) from e
            LOG.error("ClientError Exception : %s", str(e))
            raise SamListUnknownClientError(msg=str(e)) from e
        except BotoCoreError as e:
            LOG.error("Botocore Exception : %s", str(e))
            raise SamListUnknownBotoCoreError(msg=str(e)) from e

    def get_translated_dict(self, template_file_dict: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Performs a sam translate on a template and returns the translated template in the form of a dictionary or
        raises exceptions accordingly

        Parameters
        ----------
        template_file_dict: Dict[Any, Any]
            The template in dictionary format to be translated

        Returns
        -------
        response: Dict[Any, Any]
            The dictionary representing the translated template
        """
        try:
            # Note to check if IAM can be mocked to get around doing a translate without it
            validator = SamTemplateValidator(
                template_file_dict,
                ManagedPolicyLoader(self.iam_client),
                profile=self.profile,
                region=self.region,
                parameter_overrides=self.parameter_overrides,
            )
            translated_dict = yaml_parse(validator.get_translated_template_if_valid())
            return translated_dict
        except InvalidSamDocumentException as e:
            raise InvalidSamTemplateException(str(e)) from e
        except NoRegionFound as no_region_found_e:
            raise UserException(
                "AWS Region was not found. Please configure your region through a profile or --region option",
                wrapped_from=no_region_found_e.__class__.__name__,
            ) from no_region_found_e
        except NoCredentialsError as e:
            raise UserException(
                "AWS Credentials are required. Please configure your credentials.", wrapped_from=e.__class__.__name__
            ) from e
        except ClientError as e:
            LOG.error("ClientError Exception : %s", str(e))
            raise SamListUnknownClientError(msg=str(e)) from e

    def produce(self):
        """
        Produces the resource data to be printed
        """
        sam_template = get_template_data(self.template_file)

        translated_dict = self.get_translated_dict(template_file_dict=sam_template)

        stacks, _ = SamLocalStackProvider.get_stacks(template_file="", template_dictionary=translated_dict)
        if not stacks or not stacks[ROOT_STACK].resources:
            raise SamListLocalResourcesNotFoundError(msg="No local resources found.")
        seen_resources = set()
        resources_list = []
        if self.stack_name:
            response = self.get_resources_info()
            for deployed_resource in response["StackResources"]:
                resource_data = ResourcesDef(
                    LogicalResourceId=deployed_resource.get("LogicalResourceId"),
                    PhysicalResourceId=deployed_resource.get("PhysicalResourceId"),
                )
                resources_list.append(dataclasses.asdict(resource_data))
                seen_resources.add(deployed_resource.get("LogicalResourceId"))
            for local_resource in stacks[ROOT_STACK].resources:
                if local_resource not in seen_resources:
                    resource_data = ResourcesDef(LogicalResourceId=local_resource, PhysicalResourceId="-")
                    resources_list.append(dataclasses.asdict(resource_data))
        else:
            for local_resource in stacks[ROOT_STACK].resources:
                # Set the PhysicalID to "-" if there is no corresponding PhysicalID
                resource_data = ResourcesDef(LogicalResourceId=local_resource, PhysicalResourceId="-")
                resources_list.append(dataclasses.asdict(resource_data))
        mapped_output = self.mapper.map(resources_list)
        self.consumer.consume(mapped_output)
