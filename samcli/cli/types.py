"""
Implementation of custom click parameter types
"""

import re
import json
from json import JSONDecodeError

import click


class CfnParameterOverridesType(click.ParamType):
    """
    Custom Click options type to accept values for CloudFormation template parameters. You can pass values for
    parameters as "ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"
    """

    __EXAMPLE = "ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"

    # Regex that parses CloudFormation parameter key-value pairs: https://regex101.com/r/xqfSjW/2
    _pattern = r"(?:ParameterKey=([A-Za-z0-9\"]+),ParameterValue=(\"(?:\\.|[^\"\\]+)*\"|(?:\\.|[^ \"\\]+)+))"

    name = ""

    def convert(self, value, param, ctx):
        result = {}
        if not value:
            return result

        groups = re.findall(self._pattern, value)
        if not groups:
            return self.fail(
                "{} is not in valid format. It must look something like '{}'".format(value, self.__EXAMPLE), param, ctx
            )

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

    _pattern = r"([A-Za-z0-9\"]+)=([A-Za-z0-9\"]+)"

    # NOTE(TheSriram): name needs to be added to click.ParamType requires it.
    name = "CfnMetadata"

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
                key, value = group
                # assign to result['KeyName1'] = string and so on.
                result[key] = value

        if fail:
            return self.fail(
                "{} is not in valid format. It must look something like '{}'".format(value, self._EXAMPLE), param, ctx
            )

        return result
