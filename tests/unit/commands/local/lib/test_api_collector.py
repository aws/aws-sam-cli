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


class TestApiCollector_dedupe_function_routes(TestCase):
    def test_preserves_options_route_with_different_authorizer(self):
        routes = [
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["ANY"],
                authorizer_name="MyAuthorizer",
            ),
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["OPTIONS"],
                authorizer_name=None,
                use_default_authorizer=False,
            ),
        ]

        actual = ApiCollector.dedupe_function_routes(routes)

        expected = [
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["GET", "DELETE", "PUT", "POST", "HEAD", "PATCH"],
                authorizer_name="MyAuthorizer",
            ),
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["OPTIONS"],
                authorizer_name=None,
                use_default_authorizer=False,
            ),
        ]

        self.assertCountEqual(expected, actual)

    def test_reconciles_overlapping_routes_with_different_operation_names(self):
        routes = [
            Route(
                function_name="func",
                path="/x",
                methods=["ANY"],
                authorizer_name="MyAuthorizer",
            ),
            Route(
                function_name="func",
                path="/x",
                methods=["OPTIONS"],
                operation_name="Preflight",
                authorizer_name=None,
                use_default_authorizer=False,
            ),
        ]

        actual = ApiCollector.dedupe_function_routes(routes)

        options_routes = [route for route in actual if "OPTIONS" in route.methods]
        protected_route = next(route for route in actual if route.authorizer_name == "MyAuthorizer")

        self.assertEqual(len(actual), 2)
        self.assertEqual(len(options_routes), 1)
        self.assertEqual(options_routes[0].methods, ["OPTIONS"])
        self.assertEqual(options_routes[0].operation_name, "Preflight")
        self.assertIsNone(options_routes[0].authorizer_name)
        self.assertFalse(options_routes[0].use_default_authorizer)
        self.assertNotIn("OPTIONS", protected_route.methods)

    def test_preserves_distinct_operation_names_for_disjoint_methods(self):
        routes = [
            Route(
                function_name="func",
                path="/x",
                methods=["GET"],
                operation_name="GetX",
            ),
            Route(
                function_name="func",
                path="/x",
                methods=["POST"],
                operation_name="PostX",
            ),
        ]

        actual = ApiCollector.dedupe_function_routes(routes)

        routes_by_operation = {route.operation_name: route for route in actual}
        self.assertEqual(len(actual), 2)
        self.assertEqual(routes_by_operation["GetX"].methods, ["GET"])
        self.assertEqual(routes_by_operation["PostX"].methods, ["POST"])

    def test_specific_operation_owns_overlap_with_same_authorizer(self):
        routes = [
            Route(
                function_name="func",
                path="/x",
                methods=["ANY"],
                authorizer_name="MyAuthorizer",
            ),
            Route(
                function_name="func",
                path="/x",
                methods=["OPTIONS"],
                operation_name="Preflight",
                authorizer_name="MyAuthorizer",
            ),
        ]

        actual = ApiCollector.dedupe_function_routes(routes)

        options_routes = [route for route in actual if "OPTIONS" in route.methods]
        broad_route = next(route for route in actual if route.operation_name is None)

        self.assertEqual(len(actual), 2)
        self.assertEqual(len(options_routes), 1)
        self.assertEqual(options_routes[0].operation_name, "Preflight")
        self.assertNotIn("OPTIONS", broad_route.methods)

    def test_preserves_cors_when_routes_split_by_authorizer(self):
        cors = object()

        routes = [
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["ANY"],
                authorizer_name="MyAuthorizer",
            ),
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["OPTIONS"],
                authorizer_name=None,
                use_default_authorizer=False,
                cors=cors,
            ),
        ]

        actual = ApiCollector.dedupe_function_routes(routes)

        self.assertEqual(len(actual), 2)
        self.assertTrue(all(route.cors is cors for route in actual))

    def test_merges_routes_with_same_resolved_authorizer(self):
        routes = [
            Route(
                function_name="func",
                path="/x",
                methods=["GET"],
                authorizer_name=None,
                use_default_authorizer=True,
            ),
            Route(
                function_name="func",
                path="/x",
                methods=["POST"],
                authorizer_name=None,
                use_default_authorizer=False,
            ),
        ]

        actual = ApiCollector.dedupe_function_routes(routes)

        self.assertEqual(len(actual), 1)
        self.assertEqual(sorted(actual[0].methods), ["GET", "POST"])

    def test_cors_normalization_does_not_readd_options_to_protected_route(self):
        routes = [
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["ANY"],
                authorizer_name="MyAuthorizer",
            ),
            Route(
                function_name="func",
                path="/{proxy+}",
                methods=["OPTIONS"],
                authorizer_name=None,
                use_default_authorizer=False,
            ),
        ]

        deduped_routes = ApiCollector.dedupe_function_routes(routes)
        actual = ApiCollector.normalize_cors_methods(deduped_routes, object())

        options_routes = [route for route in actual if "OPTIONS" in route.methods]

        self.assertEqual(len(options_routes), 1)
        self.assertIsNone(options_routes[0].authorizer_name)

    def test_cors_normalization_groups_routes_across_operation_names(self):
        authorizer = Authorizer(
            authorizer_name="MyAuthorizer",
            type="request",
            payload_version="1.0",
        )
        routes = [
            Route(
                function_name="func",
                path="/x",
                methods=["GET"],
                operation_name="GetX",
                authorizer_name="MyAuthorizer",
                authorizer_object=authorizer,
            ),
            Route(
                function_name="func",
                path="/x",
                methods=["POST"],
                operation_name="PostX",
                authorizer_name=None,
                use_default_authorizer=False,
            ),
        ]

        actual = ApiCollector.normalize_cors_methods(routes, object())

        options_routes = [route for route in actual if "OPTIONS" in route.methods]
        self.assertEqual(len(options_routes), 1)
        self.assertEqual(options_routes[0].operation_name, "PostX")
        self.assertIsNone(options_routes[0].authorizer_object)

    @parameterized.expand(
        [
            ("protected_first", ["GET", "POST"]),
            ("unprotected_first", ["POST", "GET"]),
        ]
    )
    def test_cors_synthesis_prefers_route_without_authorizer(self, _, method_order):
        collector = ApiCollector()
        authorizer = Authorizer(
            authorizer_name="MyAuthorizer",
            type="request",
            payload_version="1.0",
        )
        routes_by_method = {
            "GET": Route(
                function_name="func",
                path="/x",
                methods=["GET"],
                authorizer_name="MyAuthorizer",
            ),
            "POST": Route(
                function_name="func",
                path="/x",
                methods=["POST"],
                authorizer_name=None,
                use_default_authorizer=False,
            ),
        }

        collector.add_authorizers("api", {"MyAuthorizer": authorizer})
        collector.add_routes("api", [routes_by_method[method] for method in method_order])
        collector.cors = object()

        actual = collector.get_api().routes
        options_routes = [route for route in actual if "OPTIONS" in route.methods]
        get_route = next(route for route in actual if "GET" in route.methods)

        self.assertEqual(len(options_routes), 1)
        self.assertIn("POST", options_routes[0].methods)
        self.assertIsNone(options_routes[0].authorizer_name)
        self.assertIsNone(options_routes[0].authorizer_object)
        self.assertNotIn("OPTIONS", get_route.methods)
        self.assertEqual(get_route.authorizer_name, "MyAuthorizer")
        self.assertIs(get_route.authorizer_object, authorizer)

    def test_cors_synthesis_falls_back_to_first_route_when_all_routes_are_authorized(self):
        first_authorizer = Authorizer(
            authorizer_name="FirstAuthorizer",
            type="request",
            payload_version="1.0",
        )
        second_authorizer = Authorizer(
            authorizer_name="SecondAuthorizer",
            type="request",
            payload_version="1.0",
        )
        routes = [
            Route(
                function_name="func",
                path="/x",
                methods=["GET"],
                authorizer_name="FirstAuthorizer",
                authorizer_object=first_authorizer,
            ),
            Route(
                function_name="func",
                path="/x",
                methods=["POST"],
                authorizer_name="SecondAuthorizer",
                authorizer_object=second_authorizer,
            ),
        ]

        actual = ApiCollector.normalize_cors_methods(ApiCollector.dedupe_function_routes(routes), object())
        options_routes = [route for route in actual if "OPTIONS" in route.methods]

        self.assertEqual(len(options_routes), 1)
        self.assertIn("GET", options_routes[0].methods)
        self.assertIs(options_routes[0].authorizer_object, first_authorizer)

    def test_preserves_payload_format_version_when_merging_routes(self):
        routes = [
            Route(
                function_name="func",
                path="/x",
                methods=["ANY"],
                event_type=Route.HTTP,
                authorizer_name=None,
            ),
            Route(
                function_name="func",
                path="/x",
                methods=["GET"],
                event_type=Route.HTTP,
                payload_format_version="1.0",
                authorizer_name=None,
            ),
        ]

        actual = ApiCollector.dedupe_function_routes(routes)

        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0].payload_format_version, "1.0")

    def test_get_api_preserves_explicit_unauthorized_options_with_cors(self):
        collector = ApiCollector()

        authorizer = Authorizer(
            authorizer_name="MyAuthorizer",
            type="request",
            payload_version="1.0",
        )

        collector.add_authorizers("api", {"MyAuthorizer": authorizer})
        collector.set_default_authorizer("api", "MyAuthorizer")

        collector.add_routes(
            "api",
            [
                Route(
                    function_name="func",
                    path="/{proxy+}",
                    methods=["ANY"],
                ),
                Route(
                    function_name="func",
                    path="/{proxy+}",
                    methods=["OPTIONS"],
                    authorizer_name=None,
                    use_default_authorizer=False,
                ),
            ],
        )

        collector.cors = object()

        api = collector.get_api()

        options_routes = [route for route in api.routes if "OPTIONS" in route.methods]
        get_routes = [route for route in api.routes if "GET" in route.methods]

        self.assertEqual(len(options_routes), 1)
        self.assertIsNone(options_routes[0].authorizer_name)

        self.assertEqual(len(get_routes), 1)
        self.assertEqual(get_routes[0].authorizer_name, "MyAuthorizer")
        self.assertIs(get_routes[0].authorizer_object, authorizer)
