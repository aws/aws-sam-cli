"""
Abstract definitions for stack builder
"""
import json
from abc import ABC
from copy import deepcopy
from typing import Dict, Union

from samcli import __version__ as VERSION

DEFAULT_TEMPLATE_BEGINNER = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Transform": "AWS::Serverless-2016-10-31",
    "Metadata": {"SamCliInfo": VERSION},
    "Resources": {},
    "Outputs": {},
}


class AbstractStackBuilder(ABC):
    """
    AbstractStackBuilder implementation which holds common methods for adding resources/properties
    and generating SAM template
    """

    _template_dict: Dict

    def __init__(self, description: str):
        self._template_dict = deepcopy(DEFAULT_TEMPLATE_BEGINNER)
        self._template_dict["Description"] = description

    def add_metadata(self, key: str, value: Union[str, Dict]) -> None:
        metadata = self._template_dict.get("Metadata", {})
        metadata["key"] = value

    def add_resource(self, resource_name: str, resource_dict: Dict) -> None:
        resources = self._template_dict.get("Resources", {})
        resources[resource_name] = resource_dict

    def add_output(self, output_name: str, output_value: Union[Dict, str]) -> None:
        outputs = self._template_dict.get("Outputs", {})
        outputs[output_name] = {"Value": output_value}

    def build_as_dict(self) -> Dict:
        return deepcopy(self._template_dict)

    def build(self) -> str:
        return json.dumps(self._template_dict, indent=2)
