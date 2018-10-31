"""Velocity template model definitions"""

from samcli.local.velocity import util


class VelocityObject(object):
    def __init__(self, adict):
        """Convert a dictionary to a class

        @param :adict Dictionary
        """
        self.__dict__.update(adict)
        for k, v in adict.items():
            if isinstance(v, dict):
                self.__dict__[k] = VelocityObject(v)

    def size(self):
        return len(self.__dict__.keys())


class BaseModel(object):
    def __init__(self, event):
        self.event = event

    def _get_param(self, param=None):
        import pytest
        pytest.set_trace()

        if param is None:
            # return everything if no specific parameter is specified
            return {
                'header': self.event.headers,
                'querystring': self.event.query_string_params,
                'path': self.event.path_parameters
            }

        # return the parameter if it exists
        # if param exists in multiple places, use hierarchy: path, query, header
        return self.event.path_parameters.get(param) \
            or self.event.get.query_string_parameters.get(param) \
            or self.event.headers.get(param)

    def _get_json_path(self, path):
        return util.get_json_path(path, self.event.body)


class ApiGatewayRequestModel(BaseModel):
    """
    Constructs an API Gateway Request Model

    The variables and helpers in this model are available for use
    by velocity template for API Gateway requests.
    """

    def to_model(self):
        return {
            "input": {
                "body": self.event.body,
                "json": self._get_json_path,
                "params": self._get_param,
                "path": self._get_json_path
            },
            "context": self.event.request_context.to_dict(),
            "util": {
                "escapeJavaScript": util.escape_javascript,
                "parseJson": util.parse_json,
                "urlEncode": util.url_encode,
                "urlDecode": util.url_decode,
                "base64Encode": util.base64_encode,
                "base64Decode": util.base64_decode
            }
        }
