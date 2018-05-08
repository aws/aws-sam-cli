"""
Converter class that handles the conversion of paths from Api Gateway to Flask and back.
"""

import re

FLASK_PATH_PARAMS = "/<path:proxy>"
APIGW_PATH_PARAMS_ESCAPED = r"/{proxy\+}"
APIGW_PATH_PARAMS = "/{proxy+}"
LEFT_BRACKET = "{"
RIGHT_BRACKET = "}"
LEFT_ANGLE_BRACKET = "<"
RIGHT_ANGLE_BRACKET = ">"

APIGW_TO_FLASK_REGEX = re.compile(APIGW_PATH_PARAMS_ESCAPED)
FLASK_TO_APIGW_REGEX = re.compile(FLASK_PATH_PARAMS)


class PathConverter(object):

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
        proxy_sub_path = APIGW_TO_FLASK_REGEX.sub(FLASK_PATH_PARAMS, path)

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
        proxy_sub_path = FLASK_TO_APIGW_REGEX.sub(APIGW_PATH_PARAMS, path)

        # Replace the '<' and '>' with '{' and '}' respectively
        return proxy_sub_path.replace(LEFT_ANGLE_BRACKET, LEFT_BRACKET).replace(RIGHT_ANGLE_BRACKET, RIGHT_BRACKET)
