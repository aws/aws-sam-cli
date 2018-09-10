"""
Implementation of custom click parameter types
"""

import re
import click


class CfnParameterOverridesType(click.ParamType):
    """
    Custom Click options type to accept values for CloudFormation template parameters. You can pass values for
    parameters as "ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"
    """

    __EXAMPLE = "ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"

    # Regex that parses CloudFormation parameter key-value pairs: https://regex101.com/r/xqfSjW/2
    _pattern = r'(?:ParameterKey=([A-Za-z0-9\"]+),ParameterValue=(\"(?:\\.|[^\"\\]+)*\"|(?:\\.|[^ \"\\]+)+))'

    name = ''

    def convert(self, value, param, ctx):
        result = {}
        if not value:
            return result

        groups = re.findall(self._pattern, value)
        if not groups:
            return self.fail(
                "{} is not in valid format. It must look something like '{}'".format(value, self.__EXAMPLE),
                param,
                ctx
            )

        # 'groups' variable is a list of tuples ex: [(key1, value1), (key2, value2)]
        for key, value in groups:
            result[self._unquote(key)] = self._unquote(value)

        return result

    @staticmethod
    def _unquote(value):
        """
        Removes wrapping double quotes and any '\ ' characters. They are usually added to preserve spaces when passing
        value thru shell.

        Ex:
            val\ ue => value
            "hel\ lo" => hello

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

