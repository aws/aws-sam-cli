import json
from unittest import TestCase

from mock import Mock

from samcli.local.apigw.local_apigw_service import LocalApigwService, Route


class TestApiGatewayServiceStageSettings(TestCase):

    def setUp(self):
        self.request_mock = Mock()
        self.request_mock.endpoint = "endpoint"
        self.request_mock.path = "route1"
        self.request_mock.method = "GET"
        self.request_mock.remote_addr = "190.0.0.0"
        self.request_mock.get_data.return_value = b"Stage Data"
        query_param_args_mock = Mock()
        query_param_args_mock.lists.return_value = {"query": ["params"]}.items()
        self.request_mock.args = query_param_args_mock
        self.request_mock.headers = {"Content-Type": "application/json", "X-Test": "Value"}
        self.request_mock.view_args = {"path": "params"}
        self.request_mock.scheme = "http"

        self.function_name = Mock()
        self.route1 = Route(['GET'], self.function_name, '/route1')
        self.route2 = Route(['GET'], self.function_name, '/route2', stage_name="Dev", stage_variables={
            "test": "data"
        })

        self.list_of_routes = [self.route1, self.route2]

        self.lambda_runner = Mock()
        self.lambda_runner.is_debugging.return_value = False

        self.stderr = Mock()
        self.service = LocalApigwService(self.list_of_routes,
                                         self.lambda_runner,
                                         port=3000,
                                         host='127.0.0.1',
                                         stderr=self.stderr)

    def test_construct_event_route_default_stage(self):
        self.request_mock.path = self.route1.path
        self.request_mock.get_data.return_value = None

        actual_event_str = LocalApigwService._construct_event(self.request_mock, 3000, binary_types=[],
                                                              route=self.route1)
        event_json = json.loads(actual_event_str)
        stage_name = event_json.get("requestContext", {}).get("stage")
        stage_variables = event_json.get("stageVariables")

        self.assertEquals(stage_name, self.route1.stage_name)
        self.assertEquals(stage_variables, self.route1.stage_variables)

    def test_construct_event_route_stage_variables(self):
        self.request_mock.path = self.route2.path
        self.request_mock.get_data.return_value = None
        actual_event_str = LocalApigwService._construct_event(self.request_mock, 3000, binary_types=[],
                                                              route=self.route2)
        event_json = json.loads(actual_event_str)
        stage_name = event_json.get("requestContext", {}).get("stage")
        stage_variables = event_json.get("stageVariables")

        self.assertEquals(stage_name, self.route2.stage_name)
        self.assertEquals(stage_variables, self.route2.stage_variables)
