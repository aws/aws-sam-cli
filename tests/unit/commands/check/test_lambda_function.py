from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.lambda_function import LambdaFunction


class TestLambdaFunction(TestCase):
    def test_class(self):
        object_mock = Mock()
        type_mock = Mock()
        name_mock = Mock()
        duration_mock = Mock()
        tps_mock = Mock()
        parents_mock = Mock()
        children_mock = Mock()
        requests_mock = Mock()
        average_duration_mock = Mock()
        memory_mock = Mock()
        memory_unit_mock = Mock()

        lambda_function = LambdaFunction(object_mock, type_mock, name_mock)

        lambda_function.duration = duration_mock
        lambda_function.tps = tps_mock
        lambda_function.parents.append(parents_mock)
        lambda_function.children.append(children_mock)
        lambda_function.number_of_requests = requests_mock
        lambda_function.average_duration = average_duration_mock
        lambda_function.allocated_memory = memory_mock
        lambda_function.allocated_memory_unit = memory_unit_mock

        self.assertEqual(duration_mock, lambda_function.duration)
        self.assertEqual(tps_mock, lambda_function.tps)
        self.assertEqual(parents_mock, lambda_function.parents[0])
        self.assertEqual(children_mock, lambda_function.children[0])
        self.assertEqual(requests_mock, lambda_function.number_of_requests)
        self.assertEqual(average_duration_mock, lambda_function.average_duration)
        self.assertEqual(memory_mock, lambda_function.allocated_memory)
        self.assertEqual(memory_unit_mock, lambda_function.allocated_memory_unit)
