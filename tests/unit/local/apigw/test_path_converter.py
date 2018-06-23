from unittest import TestCase

from samcli.local.apigw.path_converter import PathConverter


class TestPathConverter_toFlask(TestCase):

    def test_single_path_param(self):
        path = "/{id}"

        flask_path = PathConverter.convert_path_to_flask(path)

        self.assertEquals(flask_path, "/<id>")

    def test_proxy_path(self):
        path = "/{proxy+}"

        flask_path = PathConverter.convert_path_to_flask(path)

        self.assertEquals(flask_path, "/<path:proxy>")

    def test_proxy_path_with_different_name(self):
        path = "/{resource+}"

        flask_path = PathConverter.convert_path_to_flask(path)

        self.assertEquals(flask_path, "/<path:resource>")

    def test_proxy_with_path_param(self):
        path = "/id/{id}/user/{proxy+}"

        flask_path = PathConverter.convert_path_to_flask(path)

        self.assertEquals(flask_path, "/id/<id>/user/<path:proxy>")

    def test_multiple_path_params(self):
        path = "/id/{id}/user/{user}"

        flask_path = PathConverter.convert_path_to_flask(path)

        self.assertEquals(flask_path, "/id/<id>/user/<user>")

    def test_no_changes_to_path(self):
        path = "/id/user"

        flask_path = PathConverter.convert_path_to_flask(path)

        self.assertEquals(flask_path, "/id/user")


class TestPathConverter_toApiGateway(TestCase):

    def test_single_path_param(self):
        path = "/<id>"

        flask_path = PathConverter.convert_path_to_api_gateway(path)

        self.assertEquals(flask_path, "/{id}")

    def test_proxy_path(self):
        path = "/<path:proxy>"

        flask_path = PathConverter.convert_path_to_api_gateway(path)

        self.assertEquals(flask_path, "/{proxy+}")

    def test_proxy_path_with_different_name(self):
        path = "/<path:resource>"

        flask_path = PathConverter.convert_path_to_api_gateway(path)

        self.assertEquals(flask_path, "/{resource+}")

    def test_proxy_with_path_param(self):
        path = "/id/<id>/user/<path:proxy>"

        flask_path = PathConverter.convert_path_to_api_gateway(path)

        self.assertEquals(flask_path, "/id/{id}/user/{proxy+}")

    def test_multiple_path_params(self):
        path = "/id/<id>/user/<user>"

        flask_path = PathConverter.convert_path_to_api_gateway(path)

        self.assertEquals(flask_path, "/id/{id}/user/{user}")

    def test_no_changes_to_path(self):
        path = "/id/user"

        flask_path = PathConverter.convert_path_to_api_gateway(path)

        self.assertEquals(flask_path, "/id/user")
