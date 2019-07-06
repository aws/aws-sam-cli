import json
import os
import uuid
from random import randint
from subprocess import Popen, PIPE

from samcli.commands.local.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver


class IntrinsicsSymbolTable(object):
    def __init__(self, parameters=None, resources=None):
        self.parameters = parameters or {}
        self.resources = resources or {}

    def verify_valid_fn_get_attribute(self, logical_id, resource_type):
        """"
        This function uses a CloudFormationResourceSpecification.json, which contains the list of attributes that can
        be allowed in an Fn::Get

        Parameters
        -----------
        logical_id: str
            This is the logical_id of the requested intrinsic's property in question.
        resource_type: str
            This is the resource_type of the requested intrinsic's property in question.

        Returns
        --------
            A boolean that verifies
        """
        with open('CloudFormationResourceSpecification.json') as json_data:
            resource_specification = json.load(json_data)
            resource = self.resources.get(logical_id, {})

            return resource_type in resource_specification.get(resource.get("Type", ""), {}).get("Attributes", {})

    def default_attribute_resolver(self, logical_id, resource_type):
        """
        This is a default attribute resolver. Currently, all this does is check if it's a valid attribute from the
        CloudFormation resource spec.

        Parameters
        -----------
        logical_id: str
            This is the logical_id of the intrinsic's property in question.
        resource_type: str
            This is the resource_type of the intrinsic's property in question.
        Return
        -------
            The resolved attribute after looking it up in the symbol table.
        """
        # TODO resolve symbol_table here and provide a default fallback
        return "${" + logical_id + "." + resource_type + "}"

    def default_ref_resolver(self, ref_value):
        sanitised_ref_value = ref_value
        if sanitised_ref_value in self.parameters:
            return self.parameters.get(sanitised_ref_value)
        if sanitised_ref_value in IntrinsicResolver.SUPPORTED_PSEUDO_TYPES:
            return self.handle_pseudo_parameters(self.parameters, sanitised_ref_value)
        if sanitised_ref_value in self.resources:
            return sanitised_ref_value
        # TODO possibly move this code into symbol table area
        return "${" + sanitised_ref_value + "}"

    def get_default_region(self):
        return "us-east-1"

    def get_region(self):
        aws_region = os.getenv("AWS_REGION")
        if not aws_region:
            aws_region = self.get_default_region()
        return aws_region

    @staticmethod
    def get_availability_zone(region):
        return IntrinsicResolver.REGIONS.get(region)

    @staticmethod
    def get_regions():
        return list(IntrinsicResolver.REGIONS.keys())

    @staticmethod
    def get_default_availability_zone():
        # TODO make a standardized availability zone
        return "us-west-1a"

    def get_pseudo_account_id(self):
        process = Popen(["aws", "sts", "get-caller-identity", "--output", "text", "--query", 'Account'],
                        stdout=PIPE)
        (output, err) = process.communicate()
        process.wait()
        account_id = None
        try:
            account_id = int(output)
        except ValueError:
            pass

        if not account_id:
            account_id = ''.join(["%s" % randint(0, 9) for _ in range(12)])
        return str(account_id)

    def handle_pseudo_parameters(self, parameters, ref_type):

        if ref_type == "AWS::AccountId":
            account_id = self.get_pseudo_account_id()
            parameters["AWS::AccountId"] = str(account_id)
            return account_id

        if ref_type == "AWS::NotificationArn":
            pass

        if ref_type == "AWS::Partition":
            pass

        if ref_type == "AWS::Region":
            # TODO add smart checking based on properties in mapping
            aws_region = self.get_region()
            parameters["AWS::Region"] = aws_region
            return aws_region

        if ref_type == "AWS::StackId":  # TODO find a way to deal with this
            stack_id = uuid.uuid4()
            parameters["AWS::StackId"] = uuid.uuid4()
            return stack_id

        if ref_type == "AWS::StackName":
            # TODO find a way to deal with this
            stack_id = uuid.uuid4()
            parameters["AWS::StackName"] = uuid.uuid4()
            return stack_id

        if ref_type == "AWS::NoValue":
            return None

        if ref_type == "AWS::URLSuffix":
            if "AWS::REGION" in parameters:
                aws_region = parameters["AWS::REGION"]
            else:
                aws_region = self.get_region()
            if aws_region == "cn-north-1":
                return "amazonaws.com.cn"
            return "amazonaws.com"
