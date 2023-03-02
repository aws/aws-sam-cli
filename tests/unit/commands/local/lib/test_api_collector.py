from unittest import TestCase
from parameterized import parameterized

from samcli.lib.providers.api_collector import ApiCollector
from samcli.local.apigw.route import Route
from samcli.local.apigw.authorizers.authorizer import Authorizer


class TestApiCollector_linking_authorizer(TestCase):
    def setUp(self):
        self.apigw_id = "apigw1"

        self.api_collector = ApiCollector()

    @parameterized.expand(
        [
            (  # test link default authorizer
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name=None,
                        use_default_authorizer=True,
                    )
                ],
                {
                    "auth1": Authorizer(authorizer_name="auth1", type="token1", payload_version="1.0"),
                    "auth2": Authorizer(authorizer_name="auth2", type="token2", payload_version="1.0"),
                },
                "auth1",
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name="auth1",
                        authorizer_object=Authorizer(authorizer_name="auth1", type="token1", payload_version="1.0"),
                        use_default_authorizer=True,
                    )
                ],
            ),
            (  # test link non existant default authorizer
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name=None,
                        use_default_authorizer=True,
                    )
                ],
                {
                    "auth1": Authorizer(authorizer_name="auth1", type="token1", payload_version="1.0"),
                    "auth2": Authorizer(authorizer_name="auth2", type="token2", payload_version="1.0"),
                },
                None,
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name=None,
                        authorizer_object=None,
                        use_default_authorizer=True,
                    )
                ],
            ),
            (  # test no authorizer defined in route
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name=None,
                        use_default_authorizer=False,
                    )
                ],
                {
                    "auth1": Authorizer(authorizer_name="auth1", type="token1", payload_version="1.0"),
                    "auth2": Authorizer(authorizer_name="auth2", type="token2", payload_version="1.0"),
                },
                "auth1",
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name=None,
                        authorizer_object=None,
                        use_default_authorizer=False,
                    )
                ],
            ),
            (  # test linking defined authorizer
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name="auth2",
                    )
                ],
                {
                    "auth1": Authorizer(authorizer_name="auth1", type="token1", payload_version="1.0"),
                    "auth2": Authorizer(authorizer_name="auth2", type="token2", payload_version="1.0"),
                },
                "auth1",
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name="auth2",
                        authorizer_object=Authorizer(authorizer_name="auth2", type="token2", payload_version="1.0"),
                    )
                ],
            ),
            (  # test linking unsupported authorizer
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name="unsupported",
                    )
                ],
                {
                    "auth1": Authorizer(authorizer_name="auth1", type="token1", payload_version="1.0"),
                    "auth2": Authorizer(authorizer_name="auth2", type="token2", payload_version="1.0"),
                },
                "auth1",
                [
                    Route(
                        function_name="func1",
                        path="path1",
                        methods=["get"],
                        stack_path="path1",
                        authorizer_name=None,
                        authorizer_object=None,
                    )
                ],
            ),
        ]
    )
    def test_link_authorizers(self, routes, authorizers, default_authorizer, expected_routes):
        self.api_collector._route_per_resource[self.apigw_id] = routes
        self.api_collector._authorizers_per_resources[self.apigw_id] = authorizers
        self.api_collector._default_authorizer_per_resource[self.apigw_id] = default_authorizer

        self.api_collector._link_authorizers()

        self.assertEqual(self.api_collector._route_per_resource, {self.apigw_id: expected_routes})
