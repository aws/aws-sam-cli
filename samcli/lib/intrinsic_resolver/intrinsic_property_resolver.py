"""
Process and simplifies CloudFormation intrinsic properties such as FN::* and Ref
"""

import base64
import copy
import logging
import re
from collections import OrderedDict

from samcli.commands._utils.template import get_template_data
from samcli.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidIntrinsicException, InvalidSymbolException
from samcli.lib.intrinsic_resolver.invalid_intrinsic_validation import (
    verify_all_list_intrinsic_type,
    verify_in_bounds,
    verify_intrinsic_type_bool,
    verify_intrinsic_type_dict,
    verify_intrinsic_type_int,
    verify_intrinsic_type_list,
    verify_intrinsic_type_str,
    verify_non_null,
    verify_number_arguments,
)

LOG = logging.getLogger(__name__)


class IntrinsicResolver:
    AWS_INCLUDE = "AWS::Include"
    SUPPORTED_MACRO_TRANSFORMATIONS = [AWS_INCLUDE]
    _PSEUDO_REGEX = r"AWS::.*?"
    _ATTRIBUTE_REGEX = r"[a-zA-Z0-9]*?\.?[a-zA-Z0-9]*?"
    _REGEX_SUB_FUNCTION = r"\$\{(" + _PSEUDO_REGEX + "||" + _ATTRIBUTE_REGEX + r")\}"

    FN_JOIN = "Fn::Join"
    FN_SPLIT = "Fn::Split"
    FN_SUB = "Fn::Sub"
    FN_SELECT = "Fn::Select"
    FN_BASE64 = "Fn::Base64"
    FN_FIND_IN_MAP = "Fn::FindInMap"
    FN_TRANSFORM = "Fn::Transform"
    FN_GET_AZS = "Fn::GetAZs"
    REF = "Ref"
    FN_GET_ATT = "Fn::GetAtt"
    FN_IMPORT_VALUE = "Fn::ImportValue"

    SUPPORTED_INTRINSIC_FUNCTIONS = [
        FN_JOIN,
        FN_SPLIT,
        FN_SUB,
        FN_SELECT,
        FN_BASE64,
        FN_FIND_IN_MAP,
        FN_TRANSFORM,
        FN_GET_AZS,
        REF,
        FN_GET_ATT,
        FN_IMPORT_VALUE,
    ]

    FN_AND = "Fn::And"
    FN_OR = "Fn::Or"
    FN_IF = "Fn::If"
    FN_EQUALS = "Fn::Equals"
    FN_NOT = "Fn::Not"

    CONDITIONAL_FUNCTIONS = [FN_AND, FN_OR, FN_IF, FN_EQUALS, FN_NOT]

    def __init__(self, template, symbol_resolver):
        """
        Initializes the Intrinsic Property class with the default intrinsic_key_function_map and
        conditional_key_function_map.

        In the future, for items like Fn::ImportValue multiple templates can be provided
        into the function.
        """
        self._template = None
        self._resources = None
        self._mapping = None
        self._parameters = None
        self._conditions = None
        self._outputs = None
        self.init_template(template)

        self._symbol_resolver = symbol_resolver

        self.intrinsic_key_function_map = self.default_intrinsic_function_map()
        self.conditional_key_function_map = self.default_conditional_key_map()

    def init_template(self, template):
        self._template = copy.deepcopy(template or {})
        self._resources = self._template.get("Resources", {})
        self._mapping = self._template.get("Mappings", {})
        self._parameters = self._template.get("Parameters", {})
        self._conditions = self._template.get("Conditions", {})
        self._outputs = self._template.get("Outputs", {})

    def default_intrinsic_function_map(self):
        """
        Returns a dictionary containing the mapping from
            Intrinsic Function Key -> Intrinsic Resolver.
        The intrinsic_resolver function has the format lambda intrinsic: some_retun_value

        Return
        -------
        A dictionary containing the mapping from Intrinsic Function Key -> Intrinsic Resolver
        """
        return {
            IntrinsicResolver.FN_JOIN: self.handle_fn_join,
            IntrinsicResolver.FN_SPLIT: self.handle_fn_split,
            IntrinsicResolver.FN_SUB: self.handle_fn_sub,
            IntrinsicResolver.FN_SELECT: self.handle_fn_select,
            IntrinsicResolver.FN_BASE64: self.handle_fn_base64,
            IntrinsicResolver.FN_FIND_IN_MAP: self.handle_find_in_map,
            IntrinsicResolver.FN_TRANSFORM: self.handle_fn_transform,
            IntrinsicResolver.FN_GET_AZS: self.handle_fn_get_azs,
            IntrinsicResolver.REF: self.handle_fn_ref,
            IntrinsicResolver.FN_GET_ATT: self.handle_fn_getatt,
            IntrinsicResolver.FN_IMPORT_VALUE: self.handle_fn_import_value,
        }

    def default_conditional_key_map(self):
        """
        Returns a dictionary containing the mapping from Conditional
            Conditional Intrinsic Function Key -> Conditional Intrinsic Resolver.
        The intrinsic_resolver function has the format lambda intrinsic: some_retun_value

        The code was split between conditionals and other intrinsic keys for readability purposes.
        Return
        -------
        A dictionary containing the mapping from Intrinsic Function Key -> Intrinsic Resolver
        """
        return {
            IntrinsicResolver.FN_AND: self.handle_fn_and,
            IntrinsicResolver.FN_OR: self.handle_fn_or,
            IntrinsicResolver.FN_IF: self.handle_fn_if,
            IntrinsicResolver.FN_EQUALS: self.handle_fn_equals,
            IntrinsicResolver.FN_NOT: self.handle_fn_not,
        }

    def set_intrinsic_key_function_map(self, function_map):
        """
        Sets the mapping from
            Conditional Intrinsic Function Key -> Conditional Intrinsic Resolver.
        The intrinsic_resolver function has the format lambda intrinsic: some_retun_value

        A user of this function can set the function map directly or can get the default_conditional_key_map directly.


        """
        self.intrinsic_key_function_map = function_map

    def set_conditional_function_map(self, function_map):
        """
        Sets the mapping from
            Conditional Intrinsic Function Key -> Conditional Intrinsic Resolver.
        The intrinsic_resolver function has the format lambda intrinsic: some_retun_value

        A user of this function can set the function map directly or can get the default_intrinsic_function_map directly

        The code was split between conditionals and other intrinsic keys for readability purposes.

        """
        self.conditional_key_function_map = function_map

    def intrinsic_property_resolver(self, intrinsic, ignore_errors, parent_function="template"):
        """
        This resolves the intrinsic of the format
        {
            intrinsic: dict
        } by calling the function with the relevant intrinsic function resolver.

        This also supports returning a string, list, boolean, int since they may be intermediate steps in the recursion
        process. No transformations are done on these.

        By default this will just return the item if non of the types match. This is because of the function
        resolve_all_attributes which will recreate the resources by processing every aspect of resource.

        This code resolves in a top down depth first fashion in order to create a functional style recursion that
        doesn't mutate any of the properties.

        Parameters
        ----------
        intrinsic : dict, str, list, bool, int
            This is an intrinsic property or an intermediate step
        ignore_errors : bool
            Whether to ignore errors
        parent_function : str
            In case there is a missing property, this is used to figure out where the property resolved is missing.
        Return
        ---------
        The simplified version of the intrinsic function. This could be a list,str,dict depending on the format required
        """
        if intrinsic is None:
            raise InvalidIntrinsicException("Missing Intrinsic property in {}".format(parent_function))
        if isinstance(intrinsic, list):
            return [self.intrinsic_property_resolver(item, ignore_errors) for item in intrinsic]
        if not isinstance(intrinsic, dict) or intrinsic == {}:
            return intrinsic

        # `intrinsic` is a dict at this point.

        keys = list(intrinsic.keys())
        key = keys[0]

        if key in self.intrinsic_key_function_map:
            intrinsic_value = intrinsic.get(key)
            return self.intrinsic_key_function_map.get(key)(intrinsic_value, ignore_errors)

        if key in self.conditional_key_function_map:
            intrinsic_value = intrinsic.get(key)
            return self.conditional_key_function_map.get(key)(intrinsic_value, ignore_errors)

        # In this case, it is a dictionary that doesn't directly contain an intrinsic resolver, we must recursively
        # resolve each of it's sub properties.
        sanitized_dict = {}
        for key, val in intrinsic.items():
            try:
                sanitized_key = self.intrinsic_property_resolver(key, ignore_errors, parent_function=parent_function)
                sanitized_val = self.intrinsic_property_resolver(val, ignore_errors, parent_function=parent_function)
                verify_intrinsic_type_str(
                    sanitized_key,
                    message="The keys of the dictionary {} in {} must all resolve to a string".format(
                        sanitized_key, parent_function
                    ),
                )
                sanitized_dict[sanitized_key] = sanitized_val
            # On any exception, leave the key:val of the orginal intact and continue on.
            # https://github.com/awslabs/aws-sam-cli/issues/1386
            except Exception:
                if ignore_errors:
                    LOG.debug("Unable to resolve property %s: %s. Leaving as is.", key, val)
                    sanitized_dict[key] = val
                else:
                    raise

        return sanitized_dict

    def resolve_template(self, ignore_errors=False):
        """
        This resolves all the attributes of the CloudFormation dictionary Resources, Outputs, Mappings, Parameters,
        Conditions.

        Return
        -------
        Return a processed template
        """
        processed_template = self._template

        if self._resources:
            processed_template["Resources"] = self.resolve_attribute(self._resources, ignore_errors)
        if self._outputs:
            processed_template["Outputs"] = self.resolve_attribute(self._outputs, ignore_errors)

        return processed_template

    def resolve_attribute(self, cloud_formation_property, ignore_errors=False):
        """
        This will parse through every entry in a CloudFormation root key and resolve them based on the symbol_resolver.
        Customers can optionally ignore resource errors and default to whatever the resource provides.

        Parameters
        -----------
        cloud_formation_property: dict
            A high Level dictionary containg either the Mappings, Resources, Outputs, or Parameters Dictionary
        ignore_errors: bool
            An option to ignore errors that are InvalidIntrinsicException and InvalidSymbolException
        Return
        -------
        A resolved template with all references possible simplified
        """
        processed_dict = OrderedDict()
        for key, val in cloud_formation_property.items():
            processed_key = self._symbol_resolver.get_translation(key) or key
            try:
                processed_resource = self.intrinsic_property_resolver(val, ignore_errors, parent_function=processed_key)
                processed_dict[processed_key] = processed_resource
            except (InvalidIntrinsicException, InvalidSymbolException) as e:
                resource_type = val.get("Type", "")
                if ignore_errors:
                    LOG.error("Unable to process properties of %s.%s", key, resource_type)
                    processed_dict[key] = val
                else:
                    raise InvalidIntrinsicException(
                        "Exception with property of {}.{}".format(key, resource_type) + ": " + str(e.args)
                    ) from e
        return processed_dict

    def handle_fn_join(self, intrinsic_value, ignore_errors):
        """
        { "Fn::Join" : [ "delimiter", [ comma-delimited list of values ] ] }
        This function will join the items in the list together based on the string using the python join.

        This intrinsic function will resolve all the objects within the function's value and check their type.

        Parameter
        ----------
        intrinsic_value: list, dict
            This is the value of the object inside the Fn::Join intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_JOIN
        )

        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_JOIN)

        delimiter = arguments[0]

        verify_intrinsic_type_str(delimiter, IntrinsicResolver.FN_JOIN, position_in_list="first")

        value_list = self.intrinsic_property_resolver(
            arguments[1], ignore_errors, parent_function=IntrinsicResolver.FN_JOIN
        )

        verify_intrinsic_type_list(
            value_list,
            IntrinsicResolver.FN_JOIN,
            message="The list of values in {} after the " "delimiter must be a list".format(IntrinsicResolver.FN_JOIN),
        )

        sanitized_value_list = [
            self.intrinsic_property_resolver(item, ignore_errors, parent_function=IntrinsicResolver.FN_JOIN)
            for item in value_list
        ]
        verify_all_list_intrinsic_type(
            sanitized_value_list, verification_func=verify_intrinsic_type_str, property_type=IntrinsicResolver.FN_JOIN
        )

        return delimiter.join(sanitized_value_list)

    def handle_fn_split(self, intrinsic_value, ignore_errors):
        """
        { "Fn::Split" : [ "delimiter", "source string" ] }
        This function will then split the source_string based on the delimiter

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
            This is the value of the object inside the Fn::Split intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_SPLIT
        )

        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_SPLIT)

        delimiter = arguments[0]

        verify_intrinsic_type_str(delimiter, IntrinsicResolver.FN_SPLIT, position_in_list="first")

        source_string = self.intrinsic_property_resolver(
            arguments[1], ignore_errors, parent_function=IntrinsicResolver.FN_SPLIT
        )

        verify_intrinsic_type_str(source_string, IntrinsicResolver.FN_SPLIT, position_in_list="second")

        return source_string.split(delimiter)

    def handle_fn_base64(self, intrinsic_value, ignore_errors):
        """
        { "Fn::Base64" : valueToEncode }
        This intrinsic function will then base64 encode the string using python's base64.

        This function will resolve all the intrinsic properties in valueToEncode
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Base64 intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        data = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_BASE64
        )

        verify_intrinsic_type_str(data, IntrinsicResolver.FN_BASE64)
        # Encoding then decoding is required to return a string of the data
        return base64.b64encode(data.encode()).decode()

    def handle_fn_select(self, intrinsic_value, ignore_errors):
        """
        { "Fn::Select" : [ index, listOfObjects ] }
        It will select the item in the listOfObjects using python's base64.
        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Select intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_SELECT
        )

        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_SELECT)

        index = self.intrinsic_property_resolver(
            arguments[0], ignore_errors, parent_function=IntrinsicResolver.FN_SELECT
        )

        verify_intrinsic_type_int(index, IntrinsicResolver.FN_SELECT)

        list_of_objects = self.intrinsic_property_resolver(
            arguments[1], ignore_errors, parent_function=IntrinsicResolver.FN_SELECT
        )
        verify_intrinsic_type_list(list_of_objects, IntrinsicResolver.FN_SELECT)

        sanitized_objects = [
            self.intrinsic_property_resolver(item, ignore_errors, parent_function=IntrinsicResolver.FN_SELECT)
            for item in list_of_objects
        ]

        verify_in_bounds(index=index, objects=sanitized_objects, property_type=IntrinsicResolver.FN_SELECT)

        return sanitized_objects[index]

    def handle_find_in_map(self, intrinsic_value, ignore_errors):
        """
        { "Fn::FindInMap" : [ "MapName", "TopLevelKey", "SecondLevelKey"] } This function will then lookup the
        specified dictionary in the Mappings dictionary as mappings[map_name][top_level_key][second_level_key].

        This intrinsic function will resolve all the objects within the function's value and check their type.

        The format of the Mappings dictionary is:
        "Mappings": {
            "map_name": {
                "top_level_key": {
                    "second_level_key": "value"
                    }
                }
            }
        }
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::FindInMap intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_FIND_IN_MAP
        )

        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_FIND_IN_MAP)

        verify_number_arguments(arguments, num=3, property_type=IntrinsicResolver.FN_FIND_IN_MAP)

        map_name = self.intrinsic_property_resolver(
            arguments[0], ignore_errors, parent_function=IntrinsicResolver.FN_FIND_IN_MAP
        )
        top_level_key = self.intrinsic_property_resolver(
            arguments[1], ignore_errors, parent_function=IntrinsicResolver.FN_FIND_IN_MAP
        )
        second_level_key = self.intrinsic_property_resolver(
            arguments[2], ignore_errors, parent_function=IntrinsicResolver.FN_FIND_IN_MAP
        )

        verify_intrinsic_type_str(map_name, IntrinsicResolver.FN_FIND_IN_MAP, position_in_list="first")
        verify_intrinsic_type_str(top_level_key, IntrinsicResolver.FN_FIND_IN_MAP, position_in_list="second")
        verify_intrinsic_type_str(second_level_key, IntrinsicResolver.FN_FIND_IN_MAP, position_in_list="third")

        map_value = self._mapping.get(map_name)
        verify_intrinsic_type_dict(
            map_value,
            IntrinsicResolver.FN_FIND_IN_MAP,
            position_in_list="first",
            message="The MapName is missing in the Mappings dictionary in Fn::FindInMap  for {}".format(map_name),
        )

        top_level_value = map_value.get(top_level_key)
        verify_intrinsic_type_dict(
            top_level_value,
            IntrinsicResolver.FN_FIND_IN_MAP,
            message="The TopLevelKey is missing in the Mappings dictionary in Fn::FindInMap "
            "for {}".format(top_level_key),
        )

        second_level_value = top_level_value.get(second_level_key)
        verify_intrinsic_type_str(
            second_level_value,
            IntrinsicResolver.FN_FIND_IN_MAP,
            message="The SecondLevelKey is missing in the Mappings dictionary in Fn::FindInMap  "
            "for {}".format(second_level_key),
        )

        return second_level_value

    def handle_fn_get_azs(self, intrinsic_value, ignore_errors):
        """
        { "Fn::GetAZs" : "" }
        { "Fn::GetAZs" : { "Ref" : "AWS::Region" } }
        { "Fn::GetAZs" : "us-east-1" }
        This intrinsic function will get the availability zones specified for the specified region. This is usually used
        with {"Ref": "AWS::Region"}. If it is an empty string, it will get the default region.

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::GetAZs intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        intrinsic_value = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_GET_AZS
        )
        verify_intrinsic_type_str(intrinsic_value, IntrinsicResolver.FN_GET_AZS)

        if not intrinsic_value:
            intrinsic_value = self._symbol_resolver.handle_pseudo_region()

        if intrinsic_value not in self._symbol_resolver.REGIONS:
            raise InvalidIntrinsicException(
                "Invalid region string passed in to {}".format(IntrinsicResolver.FN_GET_AZS)
            )

        return self._symbol_resolver.REGIONS.get(intrinsic_value)

    def handle_fn_transform(self, intrinsic_value, ignore_errors):
        """
        { "Fn::Transform" : { "Name" : macro name, "Parameters" : {key : value, ... } } }
        This intrinsic function will transform the data with the body provided

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Transform intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        macro_name = intrinsic_value.get("Name")
        name = self.intrinsic_property_resolver(
            macro_name, ignore_errors, parent_function=IntrinsicResolver.FN_TRANSFORM
        )

        if name not in IntrinsicResolver.SUPPORTED_MACRO_TRANSFORMATIONS:
            raise InvalidIntrinsicException(
                "The type {} is not currently supported in {}".format(name, IntrinsicResolver.FN_TRANSFORM)
            )

        parameters = intrinsic_value.get("Parameters")
        verify_intrinsic_type_dict(
            parameters, IntrinsicResolver.FN_TRANSFORM, message=" Fn::Transform requires parameters section"
        )

        location = self.intrinsic_property_resolver(parameters.get("Location"), ignore_errors)
        location_data = get_template_data(location)

        return location_data

    @staticmethod
    def handle_fn_import_value(intrinsic_value, ignore_errors):
        """
        { "Fn::ImportValue" : sharedValueToImport }
        This intrinsic function requires handling multiple stacks, which is not currently supported by SAM-CLI.
        Thus, it will thrown an exception.

        Return
        -------
        An InvalidIntrinsicException
        """
        raise InvalidIntrinsicException("Fn::ImportValue is currently not supported by IntrinsicResolver")

    def handle_fn_getatt(self, intrinsic_value, ignore_errors):
        """
        { "Fn::GetAtt" : [ "logicalNameOfResource", "attributeName" ] }
        This intrinsic function gets the attribute for logical_resource specified. Each attribute might have a different
        functionality depending on the type.

        This intrinsic function will resolve all the objects within the function's value and check their type.
        This calls the symbol resolver in order to resolve the relevant attribute.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::GetAtt intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_GET_ATT
        )
        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_GET_ATT)
        verify_number_arguments(arguments, IntrinsicResolver.FN_GET_ATT, num=2)

        logical_id = self.intrinsic_property_resolver(
            arguments[0], ignore_errors, parent_function=IntrinsicResolver.FN_GET_ATT
        )
        resource_type = self.intrinsic_property_resolver(
            arguments[1], ignore_errors, parent_function=IntrinsicResolver.FN_GET_ATT
        )

        verify_intrinsic_type_str(logical_id, IntrinsicResolver.FN_GET_ATT)
        verify_intrinsic_type_str(resource_type, IntrinsicResolver.FN_GET_ATT)

        return self._symbol_resolver.resolve_symbols(logical_id, resource_type)

    def handle_fn_ref(self, intrinsic_value, ignore_errors):
        """
        {"Ref": "Logical ID"}
        This intrinsic function gets the reference to a certain attribute. Some Ref's have different functionality with
        different resource types.

        This intrinsic function will resolve all the objects within the function's value and check their type.
        This calls the symbol resolver in order to resolve the relevant attribute.
        Parameter
        ----------
        intrinsic_value: str
           This is the value of the object inside the Ref intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.REF
        )
        verify_intrinsic_type_str(arguments, IntrinsicResolver.REF)

        return self._symbol_resolver.resolve_symbols(arguments, IntrinsicResolver.REF)

    def handle_fn_sub(self, intrinsic_value, ignore_errors):
        """
        { "Fn::Sub" : [ String, { Var1Name: Var1Value, Var2Name: Var2Value } ] } or { "Fn::Sub" : String }
        This intrinsic function will substitute the variables specified in the list into the string provided. The string
        will also parse out pseudo properties and anything of the form ${}.

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Join intrinsic function property

        Return
        -------
        A string with the resolved attributes
        """

        def resolve_sub_attribute(intrinsic_item, symbol_resolver):
            if "." in intrinsic_item:
                (logical_id, attribute_type) = intrinsic_item.rsplit(".", 1)
            else:
                (logical_id, attribute_type) = intrinsic_item, IntrinsicResolver.REF
            return symbol_resolver.resolve_symbols(logical_id, attribute_type, ignore_errors=True)

        if isinstance(intrinsic_value, str):
            intrinsic_value = [intrinsic_value, {}]

        verify_intrinsic_type_list(
            intrinsic_value, IntrinsicResolver.FN_SUB, message="The arguments to a Fn::Sub must be a list or a string"
        )

        verify_number_arguments(intrinsic_value, IntrinsicResolver.FN_SUB, num=2)

        sub_str = self.intrinsic_property_resolver(
            intrinsic_value[0], ignore_errors, parent_function=IntrinsicResolver.FN_SUB
        )
        verify_intrinsic_type_str(sub_str, IntrinsicResolver.FN_SUB, position_in_list="first")

        variables = intrinsic_value[1]
        verify_intrinsic_type_dict(variables, IntrinsicResolver.FN_SUB, position_in_list="second")

        sanitized_variables = self.intrinsic_property_resolver(
            variables, ignore_errors, parent_function=IntrinsicResolver.FN_SUB
        )

        subable_props = re.findall(string=sub_str, pattern=IntrinsicResolver._REGEX_SUB_FUNCTION)
        for sub_item in subable_props:
            sanitized_item = sanitized_variables[sub_item] if sub_item in sanitized_variables else sub_item
            result = resolve_sub_attribute(sanitized_item, self._symbol_resolver)
            sub_str = re.sub(pattern=r"\$\{" + sub_item + r"\}", string=sub_str, repl=str(result))
        return sub_str

    def handle_fn_if(self, intrinsic_value, ignore_errors):
        """
        {"Fn::If": [condition_name, value_if_true, value_if_false]}
        This intrinsic function will evaluate the condition from the Conditions dictionary and then return value_if_true
        or value_if_false depending on the value.

        The Conditions dictionary will have the following format:
        {
            "Conditions": {
                "condition_name": True/False or "{Intrinsic Function}"
            }
        }

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Join intrinsic function property

        Return
        -------
        This will return value_if_true and value_if_false depending on how the condition is evaluated
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_IF
        )
        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_IF)
        verify_number_arguments(arguments, IntrinsicResolver.FN_IF, num=3)

        condition_name = self.intrinsic_property_resolver(
            arguments[0], ignore_errors, parent_function=IntrinsicResolver.FN_IF
        )
        verify_intrinsic_type_str(condition_name, IntrinsicResolver.FN_IF)

        value_if_true = self.intrinsic_property_resolver(
            arguments[1], ignore_errors, parent_function=IntrinsicResolver.FN_IF
        )
        value_if_false = self.intrinsic_property_resolver(
            arguments[2], ignore_errors, parent_function=IntrinsicResolver.FN_IF
        )

        condition = self._conditions.get(condition_name)
        verify_intrinsic_type_dict(
            condition,
            IntrinsicResolver.FN_IF,
            message="The condition is missing in the Conditions dictionary for {}".format(IntrinsicResolver.FN_IF),
        )

        condition_evaluated = self.intrinsic_property_resolver(
            condition, ignore_errors, parent_function=IntrinsicResolver.FN_IF
        )
        verify_intrinsic_type_bool(
            condition_evaluated,
            IntrinsicResolver.FN_IF,
            message="The result of {} must evaluate to bool".format(IntrinsicResolver.FN_IF),
        )

        return value_if_true if condition_evaluated else value_if_false

    def handle_fn_equals(self, intrinsic_value, ignore_errors):
        """
        {"Fn::Equals" : ["value_1", "value_2"]}
        This intrinsic function will verify that both items in the intrinsic function are equal after resolving them.

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Join intrinsic function property

        Return
        -------
        A boolean depending on if both arguments is equal
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_EQUALS
        )
        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_EQUALS)
        verify_number_arguments(arguments, IntrinsicResolver.FN_EQUALS, num=2)

        value_1 = self.intrinsic_property_resolver(
            arguments[0], ignore_errors, parent_function=IntrinsicResolver.FN_EQUALS
        )
        value_2 = self.intrinsic_property_resolver(
            arguments[1], ignore_errors, parent_function=IntrinsicResolver.FN_EQUALS
        )
        return value_1 == value_2

    def handle_fn_not(self, intrinsic_value, ignore_errors):
        """
        {"Fn::Not": [{condition}]}
        This intrinsic function will negate the evaluation of the condition specified.

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Join intrinsic function property

        Return
        -------
        A boolean that is the opposite of the condition evaluated
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_NOT
        )
        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_NOT)
        verify_number_arguments(arguments, IntrinsicResolver.FN_NOT, num=1)
        argument_sanitised = self.intrinsic_property_resolver(
            arguments[0], ignore_errors, parent_function=IntrinsicResolver.FN_NOT
        )
        if isinstance(argument_sanitised, dict) and "Condition" in arguments[0]:
            condition_name = argument_sanitised.get("Condition")
            verify_intrinsic_type_str(condition_name, IntrinsicResolver.FN_NOT)

            condition = self._conditions.get(condition_name)
            verify_non_null(condition, IntrinsicResolver.FN_NOT, position_in_list="first")

            argument_sanitised = self.intrinsic_property_resolver(
                condition, ignore_errors, parent_function=IntrinsicResolver.FN_NOT
            )

        verify_intrinsic_type_bool(
            argument_sanitised,
            IntrinsicResolver.FN_NOT,
            message="The result of {} must evaluate to bool".format(IntrinsicResolver.FN_NOT),
        )
        return not argument_sanitised

    @staticmethod
    def get_prefix_position_in_list(i):
        """
        Gets the prefix for the string "ith element of the list", handling first, second, and third.
        :param i:
        :return:
        """
        first, second, third = 1, 2, 3
        prefix = "{} th ".format(str(i))
        if i == first:
            prefix = "first "
        elif i == second:
            prefix = "second "
        elif i == third:
            prefix = "third "
        return prefix

    def handle_fn_and(self, intrinsic_value, ignore_errors):
        """
        {"Fn::And": [{condition}, {...}]}
        This intrinsic checks that every item in the list evaluates to a boolean. The items in the list can either
        be of the format {Condition: condition_name} which finds and evaluates the Conditions dictionary of another
        intrinsic function.

        The Conditions dictionary will have the following format:
        {
            "Conditions": {
                "condition_name": True/False or "{Intrinsic Function}"
            }
        }

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Join intrinsic function property

        Return
        -------
        A boolean depending on if all of the properties in Fn::And evaluate to True
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_AND
        )
        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_AND)

        for i, argument in enumerate(arguments):
            if isinstance(argument, dict) and "Condition" in argument:
                condition_name = argument.get("Condition")
                verify_intrinsic_type_str(condition_name, IntrinsicResolver.FN_AND)

                condition = self._conditions.get(condition_name)
                verify_non_null(
                    condition, IntrinsicResolver.FN_AND, position_in_list=self.get_prefix_position_in_list(i)
                )

                condition_evaluated = self.intrinsic_property_resolver(
                    condition, ignore_errors, parent_function=IntrinsicResolver.FN_AND
                )
                verify_intrinsic_type_bool(condition_evaluated, IntrinsicResolver.FN_AND)

                if not condition_evaluated:
                    return False
            else:
                condition = self.intrinsic_property_resolver(
                    argument, ignore_errors, parent_function=IntrinsicResolver.FN_AND
                )
                verify_intrinsic_type_bool(condition, IntrinsicResolver.FN_AND)

                if not condition:
                    return False

        return True

    def handle_fn_or(self, intrinsic_value, ignore_errors):
        """
        {"Fn::Or": [{condition}, {...}]}
        This intrinsic checks that a single item in the list evaluates to a boolean. The items in the list can either
        be of the format {Condition: condition_name} which finds and evaluates the Conditions dictionary of another
        intrinsic function.

        The Conditions dictionary will have the following format:
        {
            "Conditions": {
                "condition_name": True/False or "{Intrinsic Function}"
            }
        }

        This intrinsic function will resolve all the objects within the function's value and check their type.
        Parameter
        ----------
        intrinsic_value: list, dict
           This is the value of the object inside the Fn::Join intrinsic function property

        Return
        -------
        A boolean depending on if any of the properties in Fn::And evaluate to True
        """
        arguments = self.intrinsic_property_resolver(
            intrinsic_value, ignore_errors, parent_function=IntrinsicResolver.FN_OR
        )
        verify_intrinsic_type_list(arguments, IntrinsicResolver.FN_OR)
        for i, argument in enumerate(arguments):
            if isinstance(argument, dict) and "Condition" in argument:
                condition_name = argument.get("Condition")
                verify_intrinsic_type_str(condition_name, IntrinsicResolver.FN_OR)

                condition = self._conditions.get(condition_name)
                verify_non_null(
                    condition, IntrinsicResolver.FN_OR, position_in_list=self.get_prefix_position_in_list(i)
                )

                condition_evaluated = self.intrinsic_property_resolver(
                    condition, ignore_errors, parent_function=IntrinsicResolver.FN_OR
                )
                verify_intrinsic_type_bool(condition_evaluated, IntrinsicResolver.FN_OR)
                if condition_evaluated:
                    return True
            else:
                condition = self.intrinsic_property_resolver(
                    argument, ignore_errors, parent_function=IntrinsicResolver.FN_OR
                )
                verify_intrinsic_type_bool(condition, IntrinsicResolver.FN_OR)
                if condition:
                    return True
        return False
