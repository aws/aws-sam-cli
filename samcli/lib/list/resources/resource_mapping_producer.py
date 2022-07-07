"""
The producer for the 'sam list resources' command
"""
from typing import Optional, Any
import dataclasses
import logging
import yaml

from botocore.exceptions import ClientError, NoCredentialsError
from samtranslator.translator.managed_policy_translator import ManagedPolicyLoader
from samtranslator.translator.arn_generator import NoRegionFound

from samcli.commands.list.exceptions import SamListLocalResourcesNotFoundError, SamListUnknownClientError
from samcli.lib.list.list_interfaces import Producer
from samcli.lib.list.resources.resources_def import ResourcesDef
from samcli.lib.translate.sam_template_validator import SamTemplateValidator
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.commands.translate.translate_utils import read_sam_file
from samcli.lib.translate.exceptions import InvalidSamDocumentException
from samcli.commands.local.cli_common.user_exceptions import InvalidSamTemplateException
from samcli.commands.exceptions import UserException

LOG = logging.getLogger(__name__)


class ResourceMappingProducer(Producer):
    def __init__(
        self,
        stack_name,
        output,
        region,
        profile,
        template_file,
        cloudformation_client,
        iam_client,
        mapper,
        consumer,
    ):
        self.stack_name = stack_name
        self.output = output
        self.region = region
        self.profile = profile
        self.template_file = template_file
        self.cloudformation_client = cloudformation_client
        self.iam_client = iam_client
        self.mapper = mapper
        self.consumer = consumer

    def get_translated_dict(self, template_file_dict: dict) -> Optional[Any]:
        try:
            validator = SamTemplateValidator(
                template_file_dict, ManagedPolicyLoader(self.iam_client), profile=self.profile, region=self.region
            )
            translated_dict = yaml.load(validator.get_translated_template_if_valid(), Loader=yaml.FullLoader)
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
        sam_template = read_sam_file(self.template_file)

        translated_dict = self.get_translated_dict(template_file_dict=sam_template)

        stacks, _ = SamLocalStackProvider.get_stacks(template_file="", template_dict=translated_dict)
        if not stacks or not stacks[0].resources:
            raise SamListLocalResourcesNotFoundError(msg="No local resources found.")
        resources_dict = {}
        for local_resource in stacks[0].resources:
            # Set the PhysicalID to "-" if there is no corresponding PhysicalID
            resources_dict[local_resource] = "-"
            resource_data = ResourcesDef(
                LogicalResourceId=local_resource, PhysicalResourceId=resources_dict[local_resource]
            )
            mapped_output = self.mapper.map(dataclasses.asdict(resource_data))
            self.consumer.consume(mapped_output)
