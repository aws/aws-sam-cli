"""
Methods to expose the event types and generate the event jsons for use in SAM CLI generate-event
"""

import base64
import json
import os
import warnings
from typing import Any, Dict, Optional
from urllib.parse import quote as url_quote

with warnings.catch_warnings():
    # https://github.com/aws/aws-sam-cli/issues/2381
    # chevron intentionally has a code snippet that could produce a SyntaxWarning
    # https://github.com/noahmorrison/chevron/blob/a0c11f66c6443ca6387c609b90d014653cd290bd/chevron/renderer.py#L75-L78
    # here we suppress the warning
    warnings.simplefilter("ignore")
    from chevron import renderer

from samcli.lib.utils.hash import str_checksum


class Events:
    """
    Events library class that loads and customizes event json files

    Methods
    ---------------
    expose_event_metadata(self):
        return the event mapping file
    generate-event(self, service_name, event_type, values_to_sub):
        load in and substitute values into json file (if necessary)
    """

    def __init__(self):
        """
        Constructor for event library
        """

        this_folder = os.path.dirname(os.path.abspath(__file__))
        file_name = os.path.join(this_folder, "event-mapping.json")
        with open(file_name) as f:
            self.event_mapping = json.load(f)

    def transform(self, tags: Dict[str, Any], values_to_sub: Dict[str, Any]) -> Dict[str, Any]:
        """
        transform (if needed) values_to_sub with given tags

        Parameters
        ----------
        tags: dict
            the values of a particular event that can be substituted
            within the event json
        values_to_sub: dict
            key/value pairs that will be substituted into the json
        Returns
        -------
        transformed_values_to_sub: dict
            the transformed (if needed) values to substitute into the json.
        """
        for tag, properties in tags.items():
            val = values_to_sub.get(tag)
            values_to_sub[tag] = self.transform_val(properties, val)
            if properties.get("children") is not None:
                children = properties.get("children")
                for child_tag, child_properties in children.items():
                    child_val = self.transform_val(child_properties, val)
                    values_to_sub[child_tag] = child_val
        return values_to_sub

    def transform_val(self, properties: Dict[str, Any], val: Optional[str]) -> str:
        """
        transform (if needed) given val with given properties

        Parameters
        ----------
        properties: dict
            set of properties to be used for transformation
        val: string or None
            the value to undergo transformation
        Returns
        -------
        transformed
            the transformed value (always a string for template rendering)
        """
        # Handle None values by using the default
        if val is None:
            val = properties.get("default", "")

        transformed = val

        # encode if needed
        encoding = properties.get("encoding")
        if encoding is not None:
            transformed = self.encode(encoding, transformed)

        # hash if needed
        hashing = properties.get("hashing")
        if hashing is not None:
            transformed = self.hash(hashing, transformed)

        # Note: dict type is handled separately in generate_event() using placeholders
        # to avoid JSON escaping issues during template rendering

        return transformed

    @staticmethod
    def encode(encoding_scheme: str, val: str) -> str:
        """
        encodes a given val with given encoding scheme

        Parameters
        ----------
        encoding_scheme: string
            the encoding scheme
        val: string
            the value to be encoded
        Returns
        -------
        encoded: string
            the encoded value
        """
        if encoding_scheme == "url":
            return url_quote(val)

        # base64 utf8
        if encoding_scheme == "base64":
            return base64.b64encode(val.encode("utf8")).decode("utf-8")

        # returns original val if encoding_scheme not recognized
        return val

    @staticmethod
    def hash(hashing_scheme: str, val: str) -> str:
        """
        hashes a given val using given hashing_scheme

        Parameters
        ----------
        hashing_scheme: string
            the hashing scheme
        val: string
            the value to be hashed
        Returns
        -------
        hashed: string
            the hashed value
        """
        if hashing_scheme == "md5":
            return str_checksum(val)

        # raise exception if hashing_scheme is unsupported
        raise ValueError("Hashing_scheme {} is not supported.".format(hashing_scheme))

    def generate_event(self, service_name: str, event_type: str, values_to_sub: Dict) -> str:
        """
        opens the event json, substitutes the values in, and
        returns the customized event json

        Parameters
        ----------
        service_name: string
            name of the top level service (S3, apigateway, etc)
        event_type: string
            name of the event underneath the service
        values_to_sub: dict
            key/value pairs to substitute into the json
        Returns
        -------
        renderer.render(): string
            string version of the custom event json
        """

        # set variables for easy calling
        tags = self.event_mapping[service_name][event_type]["tags"]

        # Store original dict-type values before transformation
        dict_type_values = {}
        for tag_name, tag_properties in tags.items():
            if tag_properties.get("type") == "dict" and tag_name in values_to_sub:
                dict_type_values[tag_name] = values_to_sub[tag_name]
                # Replace with a placeholder for safe template rendering
                values_to_sub[tag_name] = f"__DICT_PLACEHOLDER_{tag_name}__"

        values_to_sub = self.transform(tags, values_to_sub)

        # construct the path to the Events json file
        this_folder = os.path.dirname(os.path.abspath(__file__))
        file_name = self.event_mapping[service_name][event_type]["filename"] + ".json"
        file_path = os.path.join(this_folder, "events", service_name, file_name)

        # open the file
        with open(file_path) as f:
            data = json.load(f)

        data = json.dumps(data, indent=2)

        # return the substituted file (A string containing the rendered template.)
        rendered = renderer.render(data, values_to_sub)

        # Parse the rendered result
        rendered_json = json.loads(rendered)

        # Replace placeholders with actual dict values
        key_map = {k.lower(): k for k in rendered_json.keys()}
        for tag_name, original_value in dict_type_values.items():
            original_key = key_map.get(tag_name.lower())
            if original_key:
                placeholder = f"__DICT_PLACEHOLDER_{tag_name}__"
                if isinstance(rendered_json[original_key], str) and rendered_json[original_key] == placeholder:
                    try:
                        # Parse the original JSON string value to a dict
                        rendered_json[original_key] = json.loads(original_value)
                    except (json.JSONDecodeError, TypeError):
                        # If parsing fails, keep the original string value
                        rendered_json[original_key] = original_value

        # Return the final JSON with proper dictionary values
        return json.dumps(rendered_json, indent=2)
