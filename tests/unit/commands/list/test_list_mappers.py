from unittest import TestCase
from samcli.lib.list.resources.resources_to_table_mapper import ResourcesToTableMapper
from samcli.lib.list.stack_outputs.stack_output_to_table_mapper import StackOutputToTableMapper
from samcli.lib.list.data_to_json_mapper import DataToJsonMapper
from samcli.commands.list.json_consumer import StringConsumerJsonOutput
from samcli.commands.list.table_consumer import StringConsumerTableOutput
from samcli.lib.list.testable_resources.testable_resources_to_table_mapper import TestableResourcesToTableMapper
from samcli.lib.list.mapper_consumer_factory import MapperConsumerFactory
from samcli.lib.list.list_interfaces import ProducersEnum


class TestStackOutputsToTableMapper(TestCase):
    def test_map(self):
        data = [{"OutputKey": "outputkey1", "OutputValue": "outputvalue1", "Description": "sample description"}]
        stack_outputs_to_table_mapper = StackOutputToTableMapper()
        output = stack_outputs_to_table_mapper.map(data)
        self.assertEqual(output._title, "Stack Outputs")


class TestResourcesToTableMapper(TestCase):
    def test_map(self):
        data = [{"LogicalResourceId": "LID_1", "PhysicalResourceId": "PID_1"}]
        resources_to_table_mapper = ResourcesToTableMapper()
        output = resources_to_table_mapper.map(data)
        self.assertEqual(output._title, "Resources")


class TestTestableResourcesToTableMapper(TestCase):
    def test_map(self):
        data = [
            {
                "LogicalResourceId": "LID_1",
                "PhysicalResourceId": "PID_1",
                "CloudEndpointOrFURL": "test.url",
                "Methods": "-",
            },
            {
                "LogicalResourceId": "LID_1",
                "PhysicalResourceId": "PID_1",
                "CloudEndpointOrFURL": ["api.url1", "api.url2"],
                "Methods": ["/hello2['get, put']", "/hello['get']"],
            },
        ]
        testable_resources_to_table_mapper = TestableResourcesToTableMapper()
        output = testable_resources_to_table_mapper.map(data)
        self.assertEqual(output._title, "Testable Resources")


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

    def test_create_testable_resources_table_output(self):
        factory = MapperConsumerFactory()
        container = factory.create(ProducersEnum.TESTABLE_RESOURCES_PRODUCER, "table")
        self.assertIsInstance(container.mapper, TestableResourcesToTableMapper)
        self.assertIsInstance(container.consumer, StringConsumerTableOutput)
