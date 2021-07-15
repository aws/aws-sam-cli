from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.LambdaFunction import LambdaFunction


class TestLambdaFunction(TestCase):
    def test_class(self):
        object_mock = Mock()
        type_mock = Mock()
        duration_mock = Mock()
        tps_mock = Mock()
        parents_mock = Mock()
        children_mock = Mock()
        requests_mock = Mock()
        average_duration_mock = Mock()
        memory_mock = Mock()
        memory_unit_mock = Mock()

        lambda_function = LambdaFunction(object_mock, type_mock)

        lambda_function.set_duration(duration_mock)
        lambda_function.set_tps(tps_mock)
        lambda_function.add_parent(parents_mock)
        lambda_function.add_child(children_mock)
        lambda_function.set_number_of_requests(requests_mock)
        lambda_function.set_average_duration(average_duration_mock)
        lambda_function.set_allocated_memory(memory_mock)
        lambda_function.set_allocated_memory_unit(memory_unit_mock)

        self.assertEqual(duration_mock, lambda_function.get_duration())
        self.assertEqual(tps_mock, lambda_function.get_tps())
        self.assertEqual(parents_mock, lambda_function.get_parents()[0])
        self.assertEqual(children_mock, lambda_function.get_children()[0])
        self.assertEqual(requests_mock, lambda_function.get_number_of_requests())
        self.assertEqual(average_duration_mock, lambda_function.get_average_duration())
        self.assertEqual(memory_mock, lambda_function.get_allocated_memory())
        self.assertEqual(memory_unit_mock, lambda_function.get_allocated_memory_unit())