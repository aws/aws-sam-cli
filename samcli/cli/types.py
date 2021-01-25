"""
Implementation of custom click parameter types
"""

import re
import json
from json import JSONDecodeError

import click

from samcli.lib.package.ecr_utils import is_ecr_url

PARAM_AND_METADATA_KEY_REGEX = """([A-Za-z0-9\\"\']+)"""


def _generate_match_regex(match_pattern, delim):
    """
    Creates a regex string based on a match pattern (also a regex) that is to be
    run on a string (which may contain escaped quotes) that is separated by delimiters.

    Parameters
    ----------
    match_pattern: (str) regex pattern to match
    delim: (str) delimiter that is respected when identifying matching groups with generated regex.

    Returns
    -------
    str: regex expression

    """

    # Non capturing groups reduces duplicates in groups, but does not reduce matches.
    return (
        f"""(\\"(?:\\\\{match_pattern}|[^\\"\\\\]+)*\\"|"""
        + f"""\'(?:\\\\{match_pattern}|[^\'\\\\]+)*\'|"""
        + f"""(?:\\\\{match_pattern}|[^{delim}\\"\\\\]+)+)"""
    )


def _unquote_wrapped_quotes(value):
    r"""
    Removes wrapping double quotes and any '\ ' characters. They are usually added to preserve spaces when passing
    value thru shell.

    Examples
    --------
    >>> _unquote_wrapped_quotes('val\ ue')
    value

    >>> _unquote_wrapped_quotes("hel\ lo")
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
        # Remove double quotes only if the string is wrapped in double quotes
        value = value.strip('"')
    elif value and (value[0] == value[-1] == "'"):
        # Remove single quotes only if the string is wrapped in single quotes
        value = value.strip("'")

    return value.replace("\\ ", " ").replace('\\"', '"').replace("\\'", "'")


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
    # Use this regex when you have space as delimiter Ex: "KeyName1=string KeyName2=string"
    VALUE_REGEX_SPACE_DELIM = _generate_match_regex(match_pattern=".", delim=" ")
    _pattern_1 = r"(?:ParameterKey={key},ParameterValue={value})".format(
        key=PARAM_AND_METADATA_KEY_REGEX, value=VALUE_REGEX_SPACE_DELIM
    )
    _pattern_2 = r"(?:(?: ){key}={value})".format(key=PARAM_AND_METADATA_KEY_REGEX, value=VALUE_REGEX_SPACE_DELIM)

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
                result[_unquote_wrapped_quotes(key)] = _unquote_wrapped_quotes(param_value)

        return result


class CfnMetadataType(click.ParamType):
    """
    Custom Click options type to accept values for metadata parameters.
    metadata parameters can be of the type KeyName1=string,KeyName2=string or {"string":"string"}
    """

    _EXAMPLE = 'KeyName1=string,KeyName2=string or {"string":"string"}'
    # Use this regex when you have comma as delimiter Ex: "KeyName1=string,KeyName2=string"
    VALUE_REGEX_COMMA_DELIM = _generate_match_regex(match_pattern=".", delim=",")

    _pattern = r"(?:{key}={value})".format(key=PARAM_AND_METADATA_KEY_REGEX, value=VALUE_REGEX_COMMA_DELIM)

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
    # Tags have additional constraints and they allow "+ - = . _ : / @" apart from alpha-numerics.
    TAG_REGEX = '[A-Za-z0-9\\"_:\\.\\/\\+-\\@=]'

    _pattern = r"{tag}={tag}".format(tag=_generate_match_regex(match_pattern=TAG_REGEX, delim=" "))

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
            # Using standard parser first.
            # We should implement other type parser like JSON and Key=key,Value=val type format.
            parsed, tags = self._standard_key_value_parser(val)
            if not parsed:
                parsed, tags = self._space_separated_key_value_parser(val)
            if parsed:
                for k in tags:
                    result[_unquote_wrapped_quotes(k)] = _unquote_wrapped_quotes(tags[k])
            else:
                groups = re.findall(self._pattern, val)

                if not groups:
                    fail = True
                for group in groups:
                    key, v = group
                    # assign to result['KeyName1'] = string and so on.
                    result[_unquote_wrapped_quotes(key)] = _unquote_wrapped_quotes(v)

            if fail:
                return self.fail(
                    "{} is not in valid format. It must look something like '{}'".format(value, self._EXAMPLE),
                    param,
                    ctx,
                )

        return result

    @staticmethod
    def _standard_key_value_parser(tag_value):
        """
        Method to parse simple `Key=Value` type tags without using regex. This is similar to how aws-cli does this.
        https://github.com/aws/aws-cli/blob/eff79a263347e8e83c8a2cc07265ab366315a992/awscli/customizations/cloudformation/deploy.py#L361
        Parameters
        ----------
        tag_value

        Returns
        -------

        """
        equals_count = tag_value.count("=")
        if equals_count != 1:
            return False, None

        splits = tag_value.split("=")
        return True, {splits[0]: splits[1]}

    @staticmethod
    def _space_separated_key_value_parser(tag_value):
        """
        Method to parse space separated `Key1=Value1 Key2=Value2` type tags without using regex.
        Parameters
        ----------
        tag_value
        """
        tags_dict = {}
        for value in tag_value.split(" "):
            parsed, parsed_tag = CfnTags._standard_key_value_parser(value)
            if not parsed:
                return False, None
            tags_dict = {**tags_dict, **parsed_tag}
        return True, tags_dict


class SigningProfilesOptionType(click.ParamType):
    """
    Custom parameter type to parse Signing Profile options
    Example options could be;
    - MyFunctionOrLayerToBeSigned=MySigningProfile
    - MyFunctionOrLayerToBeSigned=MySigningProfile:MyProfileOwner

    See convert function docs for details
    """

    pattern = r"(?:(?: )([A-Za-z0-9\"]+)=(\"(?:\\.|[^\"\\]+)*\"|(?:\\.|[^ \"\\]+)+))"

    # Note: this is required, otherwise it is failing when running help
    name = ""

    def convert(self, value, param, ctx):
        """
        Converts given Signing Profile options to a dictionary where Function or Layer name would be key,
        and signing profile details would be the value.

        Since this method is also been used when we are reading the config details from samconfig.toml,
        If value is already a dictionary, don't need to do anything, just return it.
        If value is an array, then each value will correspond to a function or layer config, and here it is parsed
        and converted into a dictionary
        """
        result = {}

        # Empty tuple
        if value == ("",):
            return result

        value = (value,) if isinstance(value, str) else value
        for val in value:
            val.strip()
            # Add empty string to start of the string to help match `_pattern2`
            val = " " + val

            signing_profiles = re.findall(self.pattern, val)

            # if no signing profiles found by regex, then fail
            if not signing_profiles:
                return self.fail(
                    f"{value} is not a valid code sign config, it should look like this 'MyFunction=SigningProfile'",
                    param,
                    ctx,
                )

            for function_name, param_value in signing_profiles:
                (signer_profile_name, signer_profile_owner) = self._split_signer_profile_name_owner(
                    _unquote_wrapped_quotes(param_value)
                )

                # code signing requires profile name, if it is not present then fail
                if not signer_profile_name:
                    return self.fail(
                        "Signer profile option has invalid format, it should look like this "
                        "MyFunction=MySigningProfile or MyFunction=MySigningProfile:MySigningProfileOwner",
                        param,
                        ctx,
                    )

                result[_unquote_wrapped_quotes(function_name)] = {
                    "profile_name": signer_profile_name,
                    "profile_owner": signer_profile_owner,
                }

        return result

    @staticmethod
    def _split_signer_profile_name_owner(signing_profile):
        equals_count = signing_profile.count(":")

        if equals_count > 1:
            return None, None
        if equals_count == 1:
            return signing_profile.split(":")
        return signing_profile, ""


class ImageRepositoryType(click.ParamType):
    """
    Custom Parameter Type for Image Repository option.
    """

    class Transformer:
        """
        Class takes in a converter (native click type) and a transformer.
        transformer is a function callback where additional transformation happens before
        conversion to a native click type.
        """

        def __init__(self, converter, transformation):
            """

            :param converter: native click Type
            :param transformation: callback function for transformation prior to conversion.
            """
            self.converter = converter
            self.transformer = transformation

        def transform(self, *args, **kwargs):
            return self.transformer(self.converter.convert(*args, **kwargs))

    # Transformation callback function checks if the received option value is a valid ECR url.
    transformer = Transformer(converter=click.STRING, transformation=is_ecr_url)
    name = ""

    def convert(self, value, param, ctx):
        """
        Attempt a conversion given the stipulations of allowed transformations.
        """
        result = self.transformer.transform(value, param, ctx)
        if not result:
            raise click.BadParameter(f"Invalid Image Repository ECR URI: {value}")
        return value


class ImageRepositoriesType(click.ParamType):
    """
    Custom Parameter Type for Multi valued Image Repositories option.
    """

    name = ""

    def convert(self, value, param, ctx):
        key_value_pair = value.split("=")
        if len(key_value_pair) != 2:
            raise click.BadParameter(
                f"{param.opts[0]} is not a valid format, it needs to be of the form function_logical_id=ECR_URI"
            )
        key = key_value_pair[0]
        _value = key_value_pair[1]
        if not is_ecr_url(_value):
            raise click.BadParameter(f"{param.opts[0]} needs to have valid ECR URI as value")
        return {key: _value}
