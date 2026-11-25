"""
Converter class that handles the conversion of paths from Api Gateway to Flask and back.
"""

import re
from typing import Any, Dict, Optional

# The regex captures any path information before the {proxy+}. This is to support paths that have other params in
# them. Otherwise the regex will match the first { with the last +} giving incorrect results.
# Example: /id/{id}/user/{proxy+}. g<1> = '/id/{id}/user/' g<2> = 'proxy'
PROXY_PATH_PARAMS_ESCAPED = r"(.*/){(.*)\+}"

# The regex replaces what was captured with PROXY_PATH_PARAMS_ESCAPED to construct the full path with the {proxy+}
# replaces. The first group is anything before {proxy+}, while the second group is the name given to the proxy.
# Example: /id/{id}/user/{resource+}; g<1> = '/id/{id}/user/'; g<2> = 'resource'
FLASK_CAPTURE_ALL_PATH = r"\g<1><path:\g<2>>"

# The regex will replace the first group from FLASK_CAPTURE_ALL_PATH_REGEX into the proxy name part of the APIGW path.
# Example: /<path:resource>; g<1> = 'resource'; output = /{resource+}
PROXY_PATH_PARAMS = r"/{\g<1>+}"

# The regex will capture the name of the path for the APIGW Proxy path.
# Example: /<path:resource> is equivalent to the APIGW path /{resource+}
FLASK_CAPTURE_ALL_PATH_REGEX = r"/<path:(.*)>"

LEFT_BRACKET = "{"
RIGHT_BRACKET = "}"
LEFT_ANGLE_BRACKET = "<"
RIGHT_ANGLE_BRACKET = ">"

APIGW_TO_FLASK_REGEX = re.compile(PROXY_PATH_PARAMS_ESCAPED)
FLASK_TO_APIGW_REGEX = re.compile(FLASK_CAPTURE_ALL_PATH_REGEX)

# Captures the name of each API Gateway path parameter and the optional '+' of a greedy parameter. Names are limited
# to the characters API Gateway allows in path segments: alphanumerics, underscores, hyphens, periods, commas, colons.
# Example: /{user-id}/{proxy+}; first match g<1> = 'user-id', g<2> = ''; second match g<1> = 'proxy', g<2> = '+'
APIGW_PATH_PARAM_REGEX = re.compile(r"{([a-zA-Z0-9_.,:-]+)(\+?)}")

# Flask only accepts variable names that are Python identifiers, so names such as {user-id} are hex encoded behind
# this prefix in the Flask path and decoded back to the original name for the API Gateway path and the Lambda event.
FLASK_VARIABLE_NAME_REGEX = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")
ENCODED_PATH_PARAM_PREFIX = "__sam_hex_"


class PathConverter:
    @staticmethod
    def convert_path_to_flask(path):
        """
        Converts a Path from an Api Gateway defined path to one that is accepted by Flask

        Examples:

        '/id/{id}' => '/id/<id>'
        '/{proxy+}' => '/<path:proxy>'

        :param str path: Path to convert to Flask defined path
        :return str: Path representing a Flask path
        """
        path = APIGW_PATH_PARAM_REGEX.sub(
            lambda match: f"{{{PathConverter._encode_param_name(match.group(1))}{match.group(2)}}}", path
        )
        proxy_sub_path = APIGW_TO_FLASK_REGEX.sub(FLASK_CAPTURE_ALL_PATH, path)

        # Replace the '{' and '}' with '<' and '>' respectively
        return proxy_sub_path.replace(LEFT_BRACKET, LEFT_ANGLE_BRACKET).replace(RIGHT_BRACKET, RIGHT_ANGLE_BRACKET)

    @staticmethod
    def convert_path_to_api_gateway(path):
        """
        Converts a Path from a Flask defined path to one that is accepted by Api Gateway

        Examples:

        '/id/<id>' => '/id/{id}'
        '/<path:proxy>' => '/{proxy+}'

        :param str path: Path to convert to Api Gateway defined path
        :return str: Path representing an Api Gateway path
        """
        proxy_sub_path = FLASK_TO_APIGW_REGEX.sub(PROXY_PATH_PARAMS, path)

        # Replace the '<' and '>' with '{' and '}' respectively
        apigw_path = proxy_sub_path.replace(LEFT_ANGLE_BRACKET, LEFT_BRACKET).replace(
            RIGHT_ANGLE_BRACKET, RIGHT_BRACKET
        )
        return APIGW_PATH_PARAM_REGEX.sub(
            lambda match: f"{{{PathConverter._decode_param_name(match.group(1))}{match.group(2)}}}", apigw_path
        )

    @staticmethod
    def convert_path_params_to_api_gateway(path_params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Converts the names of the path parameters Flask matched (request.view_args) back to the names
        defined in the Api Gateway path

        Example: {'__sam_hex_757365722d6964': '1'} => {'user-id': '1'}

        :param dict path_params: Path parameters keyed by their Flask variable names
        :return dict: Path parameters keyed by their Api Gateway names
        """
        if not path_params:
            return path_params
        return {PathConverter._decode_param_name(name): value for name, value in path_params.items()}

    @staticmethod
    def _encode_param_name(name: str) -> str:
        if FLASK_VARIABLE_NAME_REGEX.fullmatch(name):
            return name
        return ENCODED_PATH_PARAM_PREFIX + name.encode("utf-8").hex()

    @staticmethod
    def _decode_param_name(name: str) -> str:
        if not name.startswith(ENCODED_PATH_PARAM_PREFIX):
            return name
        return bytes.fromhex(name[len(ENCODED_PATH_PARAM_PREFIX) :]).decode("utf-8")
