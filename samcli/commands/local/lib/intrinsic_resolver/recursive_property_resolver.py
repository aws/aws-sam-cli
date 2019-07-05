import re
from functools import partial
from pprint import pprint
from subprocess import Popen, PIPE
from random import randint, choice

from flask import json
from six import string_types
import base64
import os
import uuid

regions = {"us-east-1": ["us-east-1a", "us-east-1b", "us-east-1c", "us-east-1d", "us-east-1e", "us-east-1f"],
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
           "cn-north-1": []}


def get_availability_zone(region):
    return regions.get(region)


def get_regions():
    return list(regions.keys())


def get_default_availability_zone():
    # TODO make a standardized availability zone
    return "us-west-1a"


SUPPORTED_MACRO_TRANSFORMATIONS = ["AWS::Include"]
_REGEX_SUB_FUNCTION = r'\$\{([A-Za-z0-9]+)\)\}'


def handle_intrinsics(template, intrinsic_obj, ref_resolver=None,
                      attribute_resolver=None):
    resources = template.get("Resources", {})
    mapping = template.get("Mapping", {})
    parameters = template.get("Parameters")
    conditions = template.get("Conditions")

    def verify_valid_attribute(resources, logical_id, resource_type):
        with open('CloudFormationResourceSpecification.json') as json_data:
            d = json.load(json_data)

            return resource_type in d.get(resources.get(logical_id, {}).get("Type", ""), {}).get("Attributes", {})

    def default_attribute_resolver(resources, logical_id, resource_type):
        if not verify_valid_attribute(resources, logical_id, resource_type):
            raise InvalidIntrinsicException(
                "Invalid Intrinsic Definition: The type {} does not have a valid associated resource "
                "property of {}".format(logical_id, resource_type))
        return "${" + logical_id + "." + resource_type + "}"
        # TODO figure out how to resolve these properties

    def default_ref_resolver(ref_value):
        sanitised_ref_value = helper(ref_value)
        if sanitised_ref_value in parameters:
            return parameters.get(sanitised_ref_value)
        if sanitised_ref_value in SUPPORTED_PSEUDO_TYPES:
            return handle_pseudo_parameters(parameters, sanitised_ref_value)
        if sanitised_ref_value in resources:
            return sanitised_ref_value
        # TODO figure out how to resolve these properties
        return "${" + sanitised_ref_value + "}"

    if not ref_resolver:
        ref_resolver = default_ref_resolver
    if not attribute_resolver:
        attribute_resolver = default_attribute_resolver

    def helper(intrinsic):
        def handle_fn_join(intrinsic_value):
            # { "Fn::Join" : [ "delimiter", [ comma-delimited list of values ] ] }
            arguments = helper(intrinsic_value)

            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to Fn::Join must be a list")

            delimiter = helper(arguments[0])

            if not isinstance(delimiter, string_types):
                raise InvalidIntrinsicException("Invalid Intrinsic Definition: The first argument in Fn::Join must be "
                                                "the delimiter and evaluated to a string")

            value_list = helper(arguments[1])

            if not isinstance(value_list, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The list of values in Fn::Join after the delimiter must be a list")

            return delimiter.join([helper(item) for item in value_list])

        def handle_fn_split(intrinsic_value):
            # { "Fn::Split" : [ "delimiter", "source string" ] }
            arguments = helper(intrinsic_value)

            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to Fn::Split must be a list")

            delimiter = helper(arguments[0])

            if not isinstance(delimiter, string_types):
                raise InvalidIntrinsicException("Invalid Intrinsic Definition: The first argument in Fn::Split must be "
                                                "the delimiter and evaluated to a string")

            source_string = helper(arguments[1])

            if not isinstance(source_string, string_types):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The second argument in the value of Fn::Split must resolve to a "
                    "string")

            return source_string.split(delimiter)

        def handle_fn_base64(intrinsic_value):
            # { "Fn::Base64" : valueToEncode }
            data = helper(intrinsic_value)
            if not isinstance(data, string_types):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic definition: The value of a Fn::Base64 must resolve to a string")

            return base64.b64encode(data.encode("utf-8"))

        def handle_fn_select(intrinsic_value):
            # { "Fn::Select" : [ index, listOfObjects ] }
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::Select must be a list")

            index = helper(arguments[0])

            if not isinstance(index, int):
                raise InvalidIntrinsicException("Invalid Intrinsic Definition: The first arguments to a Fn::Select "
                                                "must resolve to an integer")

            objects = [helper(item) for item in helper(arguments[1:])]

            if index < 0 or index >= len(objects):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The index of the resolved properties must be within the range")

            return objects[index]

        def handle_find_in_map(intrinsic_value):
            # { "Fn::FindInMap" : [ "MapName", "TopLevelKey", "SecondLevelKey"] }
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::FindInMap must be a list")

            if not len(arguments) == 3:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::FindInMap must have three arguments of "
                    "map_name, top_level_key, and second_level_key")

            map_name = helper(arguments[0])
            top_level_key = helper(arguments[1])
            second_level_key = helper(arguments[2])

            map_value = mapping.get(map_name)

            if not map_value:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The first arguments to a Fn::FindInMap is missing the map value "
                    "property. "
                    "The properties of Fn::FindInMap are map_name, top_level_key, and second_level_key")

            top_level_value = map_value.get(top_level_key)

            if not top_level_value:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The second arguments to a Fn::FindInMap is missing the "
                    "top_level_key property. "
                    "The properties of Fn::FindInMap are map_name, top_level_key, and second_level_key")

            second_level_value = top_level_value.get(second_level_key)

            if not second_level_value:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The second arguments to a Fn::FindInMap is missing the "
                    "second_level_key property. "
                    "The properties of Fn::FindInMap are map_name, top_level_key, and second_level_key")

            return second_level_value

        def handle_fn_azs(intrinsic_value):
            try:
                intrinsic_value = helper(intrinsic_value)
            except InvalidIntrinsicException:
                raise InvalidIntrinsicException("Invalid Intrinsic Definition: Fn::GetAzs is either missing the "
                                                "region or has the wrong ref propert")
            if not intrinsic_value or not isinstance(intrinsic_value, string_types):
                raise InvalidIntrinsicException("Invalid region string passed in")

            return get_availability_zone(intrinsic_value)

        def handle_fn_transform(intrinsic_value):
            name = helper(intrinsic_value.get("Name"))
            if name not in SUPPORTED_MACRO_TRANSFORMATIONS:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The type {} is not currently supported in Fn::Transform".format(
                        name))
            if name == "AWS::Include":
                parameters = intrinsic_value.get("Parameters", {})
                if not parameters:
                    raise InvalidIntrinsicException(
                        "Invalid Intrinsic Definition: Fn::Transform requires paramaters section")
                location = helper(parameters.get("Location"))
                return location

        def handle_fn_getatt(intrinsic_value):
            # { "Fn::GetAtt" : [ "logicalNameOfResource", "attributeName" ] }
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::FindInMap must be a list")

            if not len(arguments) == 2:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::FindInMap must have three arguments of "
                    "map_name, top_level_key, and second_level_key")

            logical_resource_id = helper(arguments[0])
            attribute_name = helper(arguments[1])
            return attribute_resolver(resources, logical_resource_id, attribute_name)

        def handle_fn_sub(intrinsic_value):
            # { "Fn::Sub" : [ String, { Var1Name: Var1Value, Var2Name: Var2Value } ] } or { "Fn::Sub" : String }
            if isinstance(intrinsic_value, string_types):
                return helper(intrinsic_value)

            if not isinstance(intrinsic_value, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::Sub must be a list or a string")

            if not len(intrinsic_value) == 2:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::Sub must have two arguments of "
                    "String, dictionary")

            sub_str_type = helper(intrinsic_value[0])
            if not isinstance(sub_str_type, string_types):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::Sub must have a string as the first argument")
            if not isinstance(intrinsic_value[1], dict):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: The arguments to a Fn::Sub must have a string as the second argument")
            sanitized_variables = {helper(key): helper(val) for key, val in intrinsic_value[1].items()}

            subable_properties = re.findall(sub_str_type, _REGEX_SUB_FUNCTION)
            for item in subable_properties:
                if item in sanitized_variables:
                    re.sub(sub_str_type, "${" + item + "}", sanitized_variables[item])
                if item in SUPPORTED_PSEUDO_TYPES:
                    re.sub(sub_str_type, "${" + item + "}", handle_pseudo_parameters(parameters, item))
            return sub_str_type

        if intrinsic is None:
            raise InvalidIntrinsicException("Invalid Intrinsic Definition: Missing object property")

        # TODO check if the string can be simplified by a !Ref. Stuff like ${} can be wrapped in the string and when to pass it back upv
        if isinstance(intrinsic, string_types) or isinstance(intrinsic, list):
            return intrinsic

        if isinstance(intrinsic, dict):
            raise InvalidIntrinsicException(
                "Invalid Intrinsic Definition: Invalid Intrinsic type. It is not a int, list, str, or dict")

        keys = list(intrinsic.keys())
        if len(keys) != 1:
            raise InvalidIntrinsicException("Invalid Intrinsic Definition")
        key = keys[0]

        if "Fn::Join" == key:
            intrinsic_value = intrinsic.get("Fn::Join")
            return handle_fn_join(intrinsic_value)

        if "Fn::Split" == key:
            intrinsic_value = intrinsic.get("Fn::Split")
            return handle_fn_split(intrinsic_value)

        if "Fn::Base64" == key:
            intrinsic_value = intrinsic.get("Fn::Base64")
            return handle_fn_base64(intrinsic_value)

        if "Fn::Select" == key:
            intrinsic_value = intrinsic.get("Fn::Select")
            return handle_fn_select(intrinsic_value)

        if "Fn::FindInMap" == key:
            intrinsic_value = intrinsic.get("Fn::FindInMap")
            return handle_find_in_map(intrinsic_value)

        if "Fn::GetAZs" == key:
            intrinsic_value = intrinsic.get("Fn::GetAZs")
            if intrinsic_value == "":
                intrinsic_value = get_default_availability_zone()
            return handle_fn_azs(intrinsic_value)

        if "Fn::Sub" == key:
            intrinsic_value = intrinsic.get("Fn::GetAZs")
            # TODO
            return handle_fn_sub(intrinsic_value)

        if "Fn::Transform" == key:
            intrinsic_value = intrinsic.get("Fn::Transform")
            return handle_fn_transform(intrinsic_value)

        if "Ref" == key:
            intrinsic_value = intrinsic.get("Ref")
            # TODO handle psuedo paramaters. Idea here is if it can't be resolved return a string with the format ${}
            #  of it. look in paramaters section and mappings section
            return ref_resolver(intrinsic_value)

        if "Fn::GetAtt" == key:
            intrinsic_value = intrinsic.get("Fn::GetAtt")

            # look in parameters section and mappings section
            return handle_fn_getatt(intrinsic_value)

        # Boolean Logic
        def handle_fn_if(intrinsic_value):
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::If requires the arguments to it to be a list")
            if len(arguments) != 3:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::If requires 3 arguments passed into the function")
            condition_name = helper(arguments[0])

            if not condition_name and isinstance(condition_name, string_types):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::If requires that the condition evaluate to a valid name")

            value_if_true = helper(arguments[1])
            value_if_false = helper(arguments[2])

            condition = conditions.get(condition_name)
            if not condition:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::If requires the first argument to be a valid condition")
            condition_evaluated = helper(condition_name)
            if not isinstance(condition_evaluated, bool):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::If condition must evaluate to a boolean")
            return value_if_true if condition_evaluated else value_if_false

        def handle_fn_and(intrinsic_value):
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Or requires the arguments to it to be a list")
            for argument in arguments:
                if isinstance(argument, dict) and "Condition" in argument:
                    condition_name = argument.get("Condition")

                    if not condition_name and isinstance(condition_name, string_types):
                        raise InvalidIntrinsicException(
                            "Invalid Intrinsic Definition: Fn::Or requires that the condition evaluate to a valid name")

                    condition = conditions.get(condition_name)

                    if not condition:
                        raise InvalidIntrinsicException(
                            "Invalid Intrinsic Definition: Fn::Or requires the first argument to be a valid condition")

                    condition_evaluated = helper(condition)
                    if not isinstance(condition_evaluated, bool):
                        raise InvalidIntrinsicException(
                            "Invalid Intrinsic Definition: Fn::Or condition must evaluate to a boolean")
                    if not condition_evaluated:
                        return False
                elif not helper(argument):
                    return False
            return True

        def handle_fn_equals(intrinsic_value):
            # TODO check if unresolved properties when dealing with booleans
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Not requires the arguments to it to be a list")
            if len(arguments) != 2:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Equals only supports two item in the list")
            return helper(arguments[0]) == helper(arguments[1])

        def handle_fn_not(intrinsic_value):
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Not requires the arguments to it to be a list")
            if len(arguments) != 1:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Not only supports one item in the list")

            condition_name = helper(arguments[0])
            if not condition_name and isinstance(condition_name, string_types):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::If requires that the condition evaluate to a valid name")

            condition = conditions.get(condition_name)

            if not condition:
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Not requires the first argument to be a valid condition")

            condition_evaluated = helper(condition)
            if not isinstance(condition_evaluated, bool):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Not condition must evaluate to a boolean")
            return not condition_evaluated

        def handle_fn_or(intrinsic_value):
            arguments = helper(intrinsic_value)
            if not isinstance(arguments, list):
                raise InvalidIntrinsicException(
                    "Invalid Intrinsic Definition: Fn::Or requires the arguments to it to be a list")
            for argument in arguments:
                if isinstance(argument, dict) and "Condition" in argument:
                    condition_name = argument.get("Condition")

                    if not condition_name and isinstance(condition_name, string_types):
                        raise InvalidIntrinsicException(
                            "Invalid Intrinsic Definition: Fn::Or requires that the condition evaluate to a valid name")

                    condition = conditions.get(condition_name)

                    if not condition:
                        raise InvalidIntrinsicException(
                            "Invalid Intrinsic Definition: Fn::Or requires the first argument to be a valid condition")

                    condition_evaluated = helper(condition)
                    if not isinstance(condition_evaluated, bool):
                        raise InvalidIntrinsicException(
                            "Invalid Intrinsic Definition: Fn::Or condition must evaluate to a boolean")
                    if condition_evaluated:
                        return True
                elif helper(argument):
                    return True
            return False

        if "Fn::And" == key:
            intrinsic_value = intrinsic.get("Fn::And")
            return handle_fn_and(intrinsic_value)

        if "Fn::Equals" == key:
            intrinsic_value = intrinsic.get("Fn::Equals")
            return handle_fn_equals(intrinsic_value)

        if "Fn::If" == key:
            intrinsic_value = intrinsic.get("Fn::If")
            return handle_fn_if(intrinsic_value)

        if "Fn::Not" == key:
            intrinsic_value = intrinsic.get("Fn::Not")
            return handle_fn_not(intrinsic_value)

        if "Fn::Or" == key:
            intrinsic_value = intrinsic.get("Fn::Or")
            return handle_fn_or(intrinsic_value)

        # this is a default case incase none of them matches
        return intrinsic

    return partial(helper, intrinsic_obj)


def get_default_region():
    return "us-east-1"


SUPPORTED_PSEUDO_TYPES = [
    "AWS::AccountId",
    "AWS::NotificationArn",
    "AWS::Partition",
    "AWS::Region",
    "AWS::StackId",
    "AWS::StackName",
    "AWS::URLSuffix"
]


def handle_pseudo_parameters(parameters, ref_type):
    def get_region():
        aws_region = os.getenv("AWS_REGION")
        if not aws_region:
            aws_region = get_default_region()
        return aws_region

    if ref_type == "AWS::AccountId":
        process = Popen(["aws", "sts", "get-caller-identity", "--output", "text", "--query", 'Account'], stdout=PIPE)
        (output, err) = process.communicate()
        process.wait()
        account_id = None
        try:
            account_id = int(output)
        except ValueError:
            pass

        if not account_id:
            account_id = ''.join(["%s" % randint(0, 9) for _ in range(12)])

        parameters["AWS::AccountId"] = str(account_id)
        return account_id

    if ref_type == "AWS::NotificationArn":
        pass

    if ref_type == "AWS::Partition":
        pass

    if ref_type == "AWS::Region":
        # TODO add smart checking based on properties in mapping
        aws_region = get_region()
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
            aws_region = get_region()
        if aws_region == "cn-north-1":
            return "amazonaws.com.cn"
        return "amazonaws.com"


class InvalidIntrinsicException(Exception):
    def __init__(self, message, *args, **kwargs):
        default_message = "Invalid Intrinsic Definition for the property"

        # if no arguments are passed set the first positional argument
        # to be the default message. To do that, we have to replace the
        # 'args' tuple with another one, that will only contain the message.
        # (we cannot do an assignment since tuples are immutable)
        if not (args or kwargs): args = (default_message,)

        # Call super constructor
        super().__init__(*args, **kwargs)


if __name__ == '__main__':
    pass
