# Copyright 2012-2015 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
"""
YAML helper, sourced from the AWS CLI

https://github.com/aws/aws-cli/blob/develop/awscli/customizations/cloudformation/yamlhelper.py
"""
# pylint: disable=too-many-ancestors

import json
from typing import cast, Dict, Optional
from botocore.compat import OrderedDict
import yaml
from samtranslator.utils.py27hash_fix import Py27Dict, Py27UniStr

# ScalarNode and SequenceNode are not declared in __all__,
# TODO: we need to double check whether they are public and stable
from yaml.resolver import ScalarNode, SequenceNode  # type: ignore

TAG_STR = "tag:yaml.org,2002:str"


def string_representer(dumper, value):
    """
    Customer Yaml representer that will force the scalar to be quoted in a yaml.dump
    if it scalar starts with a 0. This is needed to keep account ids a string instead
    of turning into on int because yaml thinks it an octal.

    Parameters
    ----------
    dumper yaml.dumper
    value str
        Value in template to resolve

    Returns
    -------

    """
    if value.startswith("0"):
        return dumper.represent_scalar(TAG_STR, value, style="'")

    return dumper.represent_scalar(TAG_STR, value)


def intrinsics_multi_constructor(loader, tag_prefix, node):
    """
    YAML constructor to parse CloudFormation intrinsics.
    This will return a dictionary with key being the instrinsic name
    """

    # Get the actual tag name excluding the first exclamation
    tag = node.tag[1:]

    # Some intrinsic functions doesn't support prefix "Fn::"
    prefix = "Fn::"
    if tag in ["Ref", "Condition"]:
        prefix = ""

    cfntag = prefix + tag

    if tag == "GetAtt" and isinstance(node.value, str):
        # ShortHand notation for !GetAtt accepts Resource.Attribute format
        # while the standard notation is to use an array
        # [Resource, Attribute]. Convert shorthand to standard format
        value = node.value.split(".", 1)

    elif isinstance(node, ScalarNode):
        # Value of this node is scalar
        value = loader.construct_scalar(node)

    elif isinstance(node, SequenceNode):
        # Value of this node is an array (Ex: [1,2])
        value = loader.construct_sequence(node)

    else:
        # Value of this node is an mapping (ex: {foo: bar})
        value = loader.construct_mapping(node)

    return {cfntag: value}


def _dict_representer(dumper, data):
    return dumper.represent_dict(data.items())


def yaml_dump(dict_to_dump):
    """
    Dumps the dictionary as a YAML document
    :param dict_to_dump:
    :return:
    """
    CfnDumper.add_representer(OrderedDict, _dict_representer)
    CfnDumper.add_representer(str, string_representer)
    CfnDumper.add_representer(Py27Dict, _dict_representer)
    CfnDumper.add_representer(Py27UniStr, string_representer)
    return yaml.dump(dict_to_dump, default_flow_style=False, Dumper=CfnDumper)


def _dict_constructor(loader, node):
    # Necessary in order to make yaml merge tags work
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))


def yaml_parse(yamlstr) -> Dict:
    """Parse a yaml string"""
    try:
        # PyYAML doesn't support json as well as it should, so if the input
        # is actually just json it is better to parse it with the standard
        # json parser.
        return cast(Dict, json.loads(yamlstr, object_pairs_hook=OrderedDict))
    except ValueError:
        yaml.SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor)
        yaml.SafeLoader.add_multi_constructor("!", intrinsics_multi_constructor)
        return cast(Dict, yaml.safe_load(yamlstr))


def parse_yaml_file(file_path, extra_context: Optional[Dict] = None) -> Dict:
    """
    Read the file, do variable substitution, parse it as JSON/YAML

    Parameters
    ----------
    file_path : string
        Path to the file to read
    extra_context : Dict
        if the file contains variable in the format of %(variableName)s i.e. the same format of the string % operator,
        this parameter provides the values for those variables substitution.

    Returns
    -------
    questions data as a dictionary
    """

    with open(file_path, "r", encoding="utf-8") as fp:
        content = fp.read()
        if isinstance(extra_context, dict):
            content = content % extra_context
        return yaml_parse(content)


class CfnDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True
