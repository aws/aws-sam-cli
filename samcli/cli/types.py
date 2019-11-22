"""
Implementation of custom click parameter types
"""

import re
import json
from json import JSONDecodeError

import click


def _value_regex(delim):
    return f'(\\"(?:\\\\.|[^\\"\\\\]+)*\\"|(?:\\\\.|[^{delim}\\"\\\\]+)+)'


KEY_REGEX = '([A-Za-z0-9\\"]+)'
# Use this regex when you have space as delimiter Ex: "KeyName1=string KeyName2=string"
VALUE_REGEX_SPACE_DELIM = _value_regex(" ")
# Use this regex when you have comma as delimiter Ex: "KeyName1=string,KeyName2=string"
VALUE_REGEX_COMMA_DELIM = _value_regex(",")


class CfnParameterOverridesType(click.ParamType):
    """
    Custom Click options type to accept values for CloudFormation template parameters. You can pass values for
    parameters as "ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"
    """

    __EXAMPLE_1 = "ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"
    __EXAMPLE_2 = "KeyPairName=MyKey InstanceType=t1.micro"

    # Regex that parses CloudFormation parameter key-value pairs:
    # https://regex101.com/r/xqfSjW/2
    # https://regex101.com/r/xqfSjW/5

    # If Both ParameterKey pattern and KeyPairName=MyKey should not be present
    # while adding parameter overrides, if they are, it
    # can result in unpredicatable behavior.
    _pattern_1 = r"(?:ParameterKey={key},ParameterValue={value})".format(key=KEY_REGEX, value=VALUE_REGEX_SPACE_DELIM)
    _pattern_2 = r"(?:(?: ){key}={value})".format(key=KEY_REGEX, value=VALUE_REGEX_SPACE_DELIM)

    ordered_pattern_match = [_pattern_1, _pattern_2]

    # NOTE(TheSriram): name needs to be added to click.ParamType requires it.
    name = ""

    def convert(self, value, param, ctx):
        result = {}

        # Empty tuple
        if value == ("",):
            return result

        value = (value,) if isinstance(value, str) else value
        for val in value:
            val.strip()
            # Add empty string to start of the string to help match `_pattern2`
            val = " " + val

            try:
                # NOTE(TheSriram): find the first regex that matched.
                # pylint is concerned that we are checking at the same `val` within the loop,
                # but that is the point, so disabling it.
                pattern = next(
                    i
                    for i in filter(
                        lambda item: re.findall(item, val), self.ordered_pattern_match
                    )  # pylint: disable=cell-var-from-loop
                )
            except StopIteration:
                return self.fail(
                    "{} is not in valid format. It must look something like '{}' or '{}'".format(
                        val, self.__EXAMPLE_1, self.__EXAMPLE_2
                    ),
                    param,
                    ctx,
                )

            groups = re.findall(pattern, val)

            # 'groups' variable is a list of tuples ex: [(key1, value1), (key2, value2)]
            for key, param_value in groups:
                result[self._unquote(key)] = self._unquote(param_value)

        return result

    @staticmethod
    def _unquote(value):
        r"""
        Removes wrapping double quotes and any '\ ' characters. They are usually added to preserve spaces when passing
        value thru shell.

        Examples
        --------
        >>> _unquote('val\ ue')
        value

        >>> _unquote("hel\ lo")
        hello

        Parameters
        ----------
        value : str
            Input to unquote

        Returns
        -------
        Unquoted string
        """
        if value and (value[0] == value[-1] == '"'):
            # Remove quotes only if the string is wrapped in quotes
            value = value.strip('"')

        return value.replace("\\ ", " ").replace('\\"', '"')


class CfnMetadataType(click.ParamType):
    """
    Custom Click options type to accept values for metadata parameters.
    metadata parameters can be of the type KeyName1=string,KeyName2=string or {"string":"string"}
    """

    _EXAMPLE = 'KeyName1=string,KeyName2=string or {"string":"string"}'

    _pattern = r"(?:{key}={value})".format(key=KEY_REGEX, value=VALUE_REGEX_COMMA_DELIM)

    # NOTE(TheSriram): name needs to be added to click.ParamType requires it.
    name = ""

    def convert(self, value, param, ctx):
        result = {}
        fail = False
        if not value:
            return result
        try:
            # Look to load the value into json if we can.
            result = json.loads(value)
            for val in result.values():
                if isinstance(val, (dict, list)):
                    # Need a non nested dictionary or a dictionary with non list values,
                    # If either is found, fail the conversion.
                    fail = True
        except JSONDecodeError:
            # if looking for a json format failed, look at if the specified value follows
            # KeyName1=string,KeyName2=string format
            groups = re.findall(self._pattern, value)

            if not groups:
                fail = True
            for group in groups:
                key, v = group
                # assign to result['KeyName1'] = string and so on.
                result[key] = v

        if fail:
            return self.fail(
                "{} is not in valid format. It must look something like '{}'".format(value, self._EXAMPLE), param, ctx
            )

        return result


class CfnTags(click.ParamType):
    """
    Custom Click options type to accept values for tag parameters.
    tag parameters can be of the type KeyName1=string KeyName2=string
    """

    _EXAMPLE = "KeyName1=string KeyName2=string"

    _pattern = r"{key}={value}".format(key=KEY_REGEX, value=VALUE_REGEX_SPACE_DELIM)

    # NOTE(TheSriram): name needs to be added to click.ParamType requires it.
    name = ""

    def convert(self, value, param, ctx):
        result = {}
        fail = False
        # Empty tuple
        if value == ("",):
            return result

        # if value comes in a via configuration file, it will be a string. So we should still convert it.
        value = (value,) if not isinstance(value, tuple) else value

        for val in value:
            groups = re.findall(self._pattern, val)

            if not groups:
                fail = True
            for group in groups:
                key, v = group
                # assign to result['KeyName1'] = string and so on.
                result[key] = v

            if fail:
                return self.fail(
                    "{} is not in valid format. It must look something like '{}'".format(value, self._EXAMPLE),
                    param,
                    ctx,
                )

        return result
