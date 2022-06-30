import pytest
import requests
from parameterized import parameterized_class

from tests.integration.local.start_api.start_api_integ_base import StartApiIntegBaseClass


@parameterized_class(
    ("template_path",),
    [
        ("/testdata/start_api/cdk/template-rest-api.yaml",),
        ("/testdata/start_api/cdk/template-open-api.yaml",),
        ("/testdata/start_api/cdk/template-http-api.yaml",),
    ],
)
class TestStartAPICDKTemplateRestAPI(StartApiIntegBaseClass):
    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_calling_proxy_endpoint(self):
        response = requests.get(self.url + "/proxypath/this/is/some/path", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_get_call_with_path_setup_with_any_implicit_api(self):
        response = requests.get(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_post_call_with_path_setup_with_any_implicit_api(self):
        response = requests.post(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_put_call_with_path_setup_with_any_implicit_api(self):
        response = requests.put(self.url + "/anyandall", json={}, timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_head_call_with_path_setup_with_any_implicit_api(self):
        response = requests.head(self.url + "/anyandall", timeout=300)
        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_delete_call_with_path_setup_with_any_implicit_api(self):
        response = requests.delete(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_options_call_with_path_setup_with_any_implicit_api(self):
        response = requests.options(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_patch_call_with_path_setup_with_any_implicit_api(self):
        response = requests.patch(self.url + "/anyandall", timeout=300)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"hello": "world"})


class TestServiceCorsRequests(StartApiIntegBaseClass):
    """
    Test to check that the correct headers are being added with Cors
    """

    template_path = "/testdata/start_api/cdk/template-cors-configs.yaml"

    def setUp(self):
        self.url = "http://127.0.0.1:{}".format(self.port)

    @pytest.mark.flaky(reruns=3)
    @pytest.mark.timeout(timeout=600, method="thread")
    def test_cors_swagger_options(self):
        """
        This tests that the Cors are added to option requests in the swagger template
        """
        response = requests.options(self.url + "/", timeout=300)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), "Content-Type,X-Amz-Date,Authorization")
        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), "GET,OPTIONS")
        self.assertEqual(response.headers.get("Access-Control-Allow-Credentials"), "true")
        self.assertEqual(response.headers.get("Access-Control-Max-Age"), "510")
