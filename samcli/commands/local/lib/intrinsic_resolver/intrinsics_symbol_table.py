"""
The symbol table that is used in IntrinsicResolver in order to resolve runtime attributes
"""
import json
import os
import uuid
from random import randint
from subprocess import Popen, PIPE, DEVNULL

from six import string_types

from samcli.commands.local.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver
from samcli.commands.local.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidSymbolException


class IntrinsicsSymbolTable(object):
    AWS_ACCOUNT_ID = "AWS::AccountId"
    AWS_NOTIFICATION_ARN = "AWS::NotificationArn"
    AWS_PARTITION = "AWS::Partition"
    AWS_REGION = "AWS::Region"
    AWS_STACK_ID = "AWS::StackId"
    AWS_STACK_NAME = "AWS::StackName"
    AWS_URL_PREFIX = "AWS::URLSuffix"
    AWS_NOVALUE = "AWS::NoValue"
    SUPPORTED_PSEUDO_TYPES = [
        AWS_ACCOUNT_ID,
        AWS_NOTIFICATION_ARN,
        AWS_PARTITION,
        AWS_REGION,
        AWS_STACK_ID,
        AWS_STACK_NAME,
        AWS_URL_PREFIX,
        AWS_NOVALUE
    ]

    DEFAULT_REGION = "us-east-1"
    REGIONS = {"us-east-1": ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1e", "us-east-1f"],
               "us-west-1": ["us-west-1b", "us-west-1c"],
               "eu-north-1": ["eu-north-1a", "eu-north-1b", "eu-north-1c"],
               "ap-northeast-3": ["ap-northeast-3a"],
               "ap-northeast-2": ["ap-northeast-2a", "ap-northeast-2b", "ap-northeast-2c"],
               "ap-northeast-1": ["ap-northeast-1a", "ap-northeast-1c", "ap-northeast-1d"],
               "sa-east-1": ["sa-east-1a", "sa-east-1c"],
               "ap-southeast-1": ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"],
               "ca-central-1": ["ca-central-1a", "ca-central-1b"],
               "ap-southeast-2": ["ap-southeast-2a", "ap-southeast-2b", "ap-southeast-2c"],
               "us-west-2": ["us-west-2a", "us-west-2b", "us-west-2c", "us-west-2d"],
               "us-east-2": ["us-east-2a", "us-east-2b", "us-east-2c"],
               "ap-south-1": ["ap-south-1a", "ap-south-1b", "ap-south-1c"],
               "eu-central-1": ["eu-central-1a", "eu-central-1b", "eu-central-1c"],
               "eu-west-1": ["eu-west-1a", "eu-west-1b", "eu-west-1c"],
               "eu-west-2": ["eu-west-2a", "eu-west-2b", "eu-west-2c"],
               "eu-west-3": ["eu-west-3a", "eu-west-3b", "eu-west-3c"],
               "cn-north-1": [],
               "us-gov-west-1": []}

    DEFAULT_PARTITION = "aws"
    GOV_PARTITION = "aws-us-gov"
    CHINA_PARTITION = "aws-cn"
    CHINA_PREFIX = "cn"
    GOV_PREFIX = "gov"

    CHINA_URL_PREFIX = "amazonaws.com.cn"
    DEFAULT_URL_PREFIX = "amazonaws.com"

    AWS_NOTIFICATION_SERVICE_NAME = "sns"
    ARN_SUFFIX = ".Arn"

    CFN_RESOURCE_TYPE = "Type"

    def __init__(self, logical_id_translator=None, parameters=None, default_type_resolver=None,
                 common_attribute_resolver=None, resources=None):
        """
        Initializes the Intrinsic Symbol Table so that runtime attributes can be resolved.

        The code is defaulted in the following order logical_id_translator => parameters => default_type_resolver =>
        common_attribute_resolver

        If the item is a pseudo type, it will run through the logical_id_translator and if it doesn't exist there
        it will generate a default one and save it in the logical_id_translator as a cache for future computation.
        Parameters
        ------------
        logical_id_translator: dict
            This will act as the default symbol table resolver. The resolver will first check if the attribute is
            explicitly defined in this dictionary and do the relevant translation.

            All Logical Ids and Pseudo types can be included here.
            {
                "RestApi.Test": {  # this could be used with RestApi.Deployment => NewRestApi
                    "Ref": "NewRestApi"
                },
                "LambdaFunction": {
                    "Ref": "LambdaFunction",
                    "Arn": "MyArn"
                }
                "AWS::Region": "us-east-1"
            }
        parameters: dict
            After the logical Id translator is checked, the parameters dictionary that is provided within the
            CloudFormation stack is used. This is usually used with the default parameter
            The format of parameters is
            "Parameters" : {
              "ParameterLogicalID" : {
                "Type" : "DataType",
                "ParameterProperty" : "value"
              }
            }
        default_type_resolver: dict
            This can be used provide common attributes that are true across all objects of a certain type.
            This can be in the format of
            {
                "AWS::ApiGateway::RestApi": {
                    "RootResourceId": "/"
                }
            }
            or can also be a function that takes in (logical_id, attribute_type) => string
            {
                "AWS::ApiGateway::RestApi": {
                    "RootResourceId": (lambda l, a, p, r: p.get("ResourceId"))
                }
            }
        common_attribute_resolver: dict
            This is a clean way of specifying common attributes across all types.
            The value can either be a function of the form string or (logical_id) => string
            {
                "Ref": lambda p,r: "",
                "Arn:": arn_resolver
            }
        """
        self.logical_id_translator = logical_id_translator or {}

        self.parameters = parameters or {}
        self.resources = resources or {}

        self.default_type_resolver = default_type_resolver or {
            "AWS::ApiGateway::RestApi": {
                "RootResourceId": "/"  # It usually used as a reference to the parent id of the RestApi,
            }
        }

        self.common_attribute_resolver = common_attribute_resolver or {
            "Ref": lambda logical_id: logical_id,
            "Arn": self.arn_resolver
        }

        self.default_pseudo_resolver = {
            IntrinsicsSymbolTable.AWS_ACCOUNT_ID: self.handle_pseudo_account_id,
            IntrinsicsSymbolTable.AWS_NOTIFICATION_ARN: self.handle_pseudo_notification_arn,
            IntrinsicsSymbolTable.AWS_PARTITION: self.handle_pseudo_partition,
            IntrinsicsSymbolTable.AWS_REGION: self.handle_pseudo_region,
            IntrinsicsSymbolTable.AWS_STACK_ID: self.handle_pseudo_stack_id,
            IntrinsicsSymbolTable.AWS_STACK_NAME: self.handle_pseudo_stack_name,
            IntrinsicsSymbolTable.AWS_NOVALUE: self.handle_pseudo_no_value,
            IntrinsicsSymbolTable.AWS_URL_PREFIX: self.handle_pseudo_url_prefix,
        }

    def resolve_symbols(self, logical_id, resource_attribute, ignore_errors=False):
        """
        This function resolves all the symbols given a logical id and a resource_attribute for Fn::GetAtt and Ref.
        This boils Ref into a type of Fn:GetAtt to simplify the implementation.
        For example:
            {"Ref": "AWS::REGION"} => resolve_symbols("AWS::REGION", "REF")
            {"Fn::GetAtt": ["logical_id", "attribute_type"] => resolve_symbols(logical_id, attribute_type)


        First pseudo types are checked. If item is present in the logical_id_translator it is returned.
        Otherwise, it falls back to the default_pseudo_resolver

        Then the default_type_resolver is checked, which has common attributes and functions for each types.
        Then the common_attribute_resolver is run, which has functions that are common for each attribute.
        Parameters
        -----------
        logical_id: str
            The logical id of the resource in question or a pseudo type.
        resource_attribute: str
            The resource attribute of the resource in question or Ref for psuedo types.
        ignore_errors: bool
            An optional flags to not return errors. This used in sub

        Return
        -------
        This resolves the attribute
        """
        # pylint: disable-msg=too-many-return-statements
        translated = self.get_translation(logical_id, resource_attribute)
        if translated:
            return translated

        if logical_id in self.SUPPORTED_PSEUDO_TYPES:
            translated = self.default_pseudo_resolver.get(logical_id)()
            self.logical_id_translator[logical_id] = translated
            return translated

        translated = self.parameters.get(logical_id, {}).get("Default")
        if translated:
            return translated

        resource_type = self.resources.get(logical_id, {}).get(IntrinsicsSymbolTable.CFN_RESOURCE_TYPE)
        resolver = self.default_type_resolver.get(resource_type, {}).get(resource_attribute) if resource_type else {}
        if resolver:
            if callable(resolver):
                return resolver(logical_id, resource_attribute)
            return resolver

        attribute_resolver = self.common_attribute_resolver.get(resource_attribute, {})
        if attribute_resolver:
            if callable(attribute_resolver):
                return attribute_resolver(logical_id)
            return attribute_resolver

        if ignore_errors:
            return "${}".format(logical_id + "." + resource_attribute)
        raise InvalidSymbolException(
            "The {} is not supported in the logical_id_translator, default_type_resolver, or the attribute_resolver."
            " It is also not a supported pseudo function".format(logical_id + "." + resource_attribute))

    def verify_valid_fn_get_attribute(self, logical_id, resource_type):
        """"
        This function uses a CloudFormationResourceSpecification.json, which contains the list of attributes that can
        be allowed in an Fn::Get.

        This is currently not used because of filepath issues

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

    def arn_resolver(self, logical_id, service_name="lambda"):
        """
        This function resolves Arn in the format
            arn:{partition_name}:{service_name}:{aws_region}:{account_id}:{function_name}

        Parameters
        -----------
        logical_id: str
            This the reference to the function name used
        service_name: str
            This is the service name used such as lambda or sns

        Return
        -------
        The resolved Arn
        """
        aws_region = self.handle_pseudo_region()
        account_id = self.handle_pseudo_account_id()
        partition_name = self.handle_pseudo_partition()
        function_name = logical_id
        function_name = self.logical_id_translator.get(function_name) or function_name
        str_format = "arn:{partition_name}:{service_name}:{aws_region}:{account_id}:{function_name}"
        if service_name == "lambda":
            str_format = "arn:{partition_name}:{service_name}:{aws_region}:{account_id}:function:{function_name}"

        return str_format.format(
            partition_name=partition_name,
            service_name=service_name,
            aws_region=aws_region,
            account_id=account_id,
            function_name=function_name)

    def get_translation(self, logical_id, resource_attributes=IntrinsicResolver.REF):
        """
        This gets the logical_id_translation of the logical id and resource_attributes.

        Parameters
        ----------
        logical_id: str
            This is the logical id of the resource in question
        resource_attributes: str
            This is the attribute required. By default, it is a REF type

        Returns
        --------
        This returns the translated item if it already exists

        """
        logical_id_item = self.logical_id_translator.get(logical_id, {})
        if isinstance(logical_id_item, string_types):
            if resource_attributes != IntrinsicResolver.REF and resource_attributes != "":
                return None
            return logical_id_item
        return logical_id_item.get(resource_attributes)

    @staticmethod
    def get_availability_zone(region):
        """
        This gets the availability zone from the the specified region

        Parameters
        -----------
        region: str
            The specified region from the SymbolTable region

        Return
        -------
        The list of availability zones for the specified region
        """
        return IntrinsicsSymbolTable.REGIONS.get(region)

    def handle_pseudo_account_id(self):
        """
        This gets the account id for the attribute AWS::AccountId.
        This calls the
        aws sts get-caller-identity --output text --query Account
        If an id cannot be found in the current system, it defaults to a random string.

        This is only run if it is not specified by the logical_id_translator as a default.

        Return
        -------
        A pseudo account id
        """
        translated = self.logical_id_translator.get(IntrinsicsSymbolTable.AWS_ACCOUNT_ID)
        if translated:
            return translated

        process = Popen(["aws", "sts", "get-caller-identity", "--output", "text", "--query", 'Account'],
                        stdout=PIPE, stderr=DEVNULL)
        (output, _) = process.communicate()
        process.wait()
        account_id = None
        try:
            account_id = int(output)
        except ValueError:
            pass

        if not account_id:
            account_id = ''.join([str(randint(0, 9)) for _ in range(12)])

        return str(account_id)

    def handle_pseudo_region(self):
        """
        Gets the region from the environment and defaults to a the default region from the global variables.

        This is only run if it is not specified by the logical_id_translator as a default.

        Return
        -------
        The region from the environment or a default one
        """
        return os.getenv("AWS_REGION") or self.DEFAULT_REGION

    def handle_pseudo_url_prefix(self):
        """
        This gets the AWS::UrlSuffix for the intrinsic with the china and regular prefix.

        This is only run if it is not specified by the logical_id_translator as a default.
        Return
        -------
        The url prefix of amazonaws.com or amazonaws.com.cn
        """
        aws_region = self.logical_id_translator.get(self.AWS_REGION) or self.handle_pseudo_region()
        if self.CHINA_PREFIX in aws_region:
            return self.CHINA_URL_PREFIX
        return self.DEFAULT_URL_PREFIX

    def handle_pseudo_notification_arn(self):
        """
        This resolves AWS::NotificationArn to return a list of random Arns.

        This is only run if it is not specified by the logical_id_translator as a default.

        Return
        -------
        A list of Notification Arns
        """
        return [self.arn_resolver(logical_id=self.get_random_string(),
                                  service_name=self.AWS_NOTIFICATION_SERVICE_NAME) for _ in range(randint(1, 3))]

    def handle_pseudo_partition(self):
        """
        This resolves AWS::Partition so that the correct partition is returned depending on the region.

        This is only run if it is not specified by the logical_id_translator as a default.

        Return
        -------
        A pseudo partition like aws-cn or aws or aws-gov
        """
        aws_region = self.logical_id_translator.get(self.AWS_REGION) or self.handle_pseudo_region()
        if self.CHINA_PREFIX in aws_region:
            return self.CHINA_PARTITION
        if self.GOV_PREFIX in aws_region:
            return self.GOV_PARTITION
        return self.DEFAULT_PARTITION

    @staticmethod
    def get_random_string():
        """
        This generates a random string to be used as defaults in functions

        Return
        -------
        A randomized string
        """
        return uuid.uuid4().hex

    def handle_pseudo_stack_id(self):
        """
        This resolves AWS::StackId by generating a random string. There is no real way to resolve this if it's not in
        the logical_id_translator

        This is only run if it is not specified by the logical_id_translator as a default.

        Return
        -------
        A randomized string
        """
        return self.get_random_string()

    def handle_pseudo_stack_name(self):
        """
        This resolves AWS::StackName by generating a random string. There is no real way to resolve this if it's not in
        the logical_id_translator

        This is only run if it is not specified by the logical_id_translator as a default.

        Return
        -------
        A randomized string
        """
        return self.get_random_string()

    @staticmethod
    def handle_pseudo_no_value():
        """
        This resolves AWS::NoValue so that it returns the python None

        Returns
        --------
        None
        :return:
        """
        return None
