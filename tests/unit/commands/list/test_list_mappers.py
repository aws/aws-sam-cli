from unittest import TestCase
from unittest.mock import patch, call
from collections import OrderedDict
from samcli.lib.list.resources.resources_to_table_mapper import ResourcesToTableMapper
from samcli.lib.list.stack_outputs.stack_output_to_table_mapper import StackOutputToTableMapper
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.commands.list.json_consumer import StringConsumerJsonOutput
from samcli.lib.list.endpoints.endpoints_to_table_mapper import EndpointsToTableMapper
from samcli.lib.list.mapper_consumer_factory import MapperConsumerFactory
from samcli.lib.list.list_interfaces import ProducersEnum
from samcli.commands.list.table_consumer import StringConsumerTableOutput


class TestStackOutputsToTableMapper(TestCase):
    def test_map(self):
        data = [{"OutputKey": "outputkey1", "OutputValue": "outputvalue1", "Description": "sample description"}]
        stack_outputs_to_table_mapper = StackOutputToTableMapper()
        output = stack_outputs_to_table_mapper.map(data)
        self.assertEqual(output.get("table_name", ""), "Stack Outputs")


class TestResourcesToTableMapper(TestCase):
    def test_map(self):
        data = [{"LogicalResourceId": "LID_1", "PhysicalResourceId": "PID_1"}]
        resources_to_table_mapper = ResourcesToTableMapper()
        output = resources_to_table_mapper.map(data)
        self.assertEqual(output.get("table_name", ""), "Resources")


class TestEndpointsToTableMapper(TestCase):
    def test_map(self):
        data = [
            {
                "LogicalResourceId": "LID_1",
                "PhysicalResourceId": "PID_1",
                "CloudEndpoint": "test.url",
                "Methods": "-",
            },
            {
                "LogicalResourceId": "LID_1",
                "PhysicalResourceId": "PID_1",
                "CloudEndpoint": "-",
                "Methods": "-",
            },
            {
                "LogicalResourceId": "LID_1",
                "PhysicalResourceId": "PID_1",
                "CloudEndpoint": ["api.url1"],
                "Methods": "-",
            },
            {
                "LogicalResourceId": "LID_1",
                "PhysicalResourceId": "PID_1",
                "CloudEndpoint": ["api.url1", "api.url2", "api.url3"],
                "Methods": ["/hello2['get, put']", "/hello['get']"],
            },
        ]
        endpoints_to_table_mapper = EndpointsToTableMapper()
        output = endpoints_to_table_mapper.map(data)
        self.assertEqual(output.get("table_name", ""), "Endpoints")


class TestMapperConsumerFactory(TestCase):
    def test_create_json_output(self):
        factory = MapperConsumerFactory()
        container = factory.create(ProducersEnum.STACK_OUTPUTS_PRODUCER, "json")
        self.assertIsInstance(container.mapper, DataToJsonMapper)
        self.assertIsInstance(container.consumer, StringConsumerJsonOutput)

    def test_create_stack_outputs_table_output(self):
        factory = MapperConsumerFactory()
        container = factory.create(ProducersEnum.STACK_OUTPUTS_PRODUCER, "table")
        self.assertIsInstance(container.mapper, StackOutputToTableMapper)
        self.assertIsInstance(container.consumer, StringConsumerTableOutput)

    def test_create_resources_table_output(self):
        factory = MapperConsumerFactory()
        container = factory.create(ProducersEnum.RESOURCES_PRODUCER, "table")
        self.assertIsInstance(container.mapper, ResourcesToTableMapper)
        self.assertIsInstance(container.consumer, StringConsumerTableOutput)

    def test_create_endpoints_table_output(self):
        factory = MapperConsumerFactory()
        container = factory.create(ProducersEnum.ENDPOINTS_PRODUCER, "table")
        self.assertIsInstance(container.mapper, EndpointsToTableMapper)
        self.assertIsInstance(container.consumer, StringConsumerTableOutput)


class TestTableConsumer(TestCase):
    @patch("samcli.commands.list.json_consumer.click.secho")
    @patch("samcli.commands.list.json_consumer.click.get_current_context")
    def test_consume(self, patched_click_get_current_context, patched_click_echo):
        consumer = StringConsumerTableOutput()
        data = {
            "format_string": "{OutputKey:<{0}} {OutputValue:<{1}} {Description:<{2}}",
            "format_args": OrderedDict(
                {"OutputKey": "OutputKey", "OutputValue": "OutputValue", "Description": "Description"}
            ),
            "table_name": "Stack Outputs",
            "data": [],
        }
        consumer.consume(data)
        print(patched_click_echo.call_args_list)
        self.assertTrue(patched_click_echo.call_args_list)
        self.assertEqual(call("Stack Outputs", bold=True), patched_click_echo.call_args_list[0])
