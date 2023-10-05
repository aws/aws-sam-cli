import json
import os
import uuid

import pytest
from pathlib import Path
from unittest import TestCase

from tests.integration.remote.test_event.remote_test_event_integ_base import RemoteTestEventIntegBase
from tests.testing_utils import run_command

# These tests only work on regions where EventBridge Schema Registry is available:
# https://docs.aws.amazon.com/general/latest/gr/eventbridgeschemas.html


@pytest.mark.xdist_group(name="sam_remote_test_event")
class TestRemoteTestEvent(RemoteTestEventIntegBase):
    # This suite uses a template from remote_invoke
    template = Path("template-multiple-lambdas.yaml")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stack_name = f"{cls.__name__}-{uuid.uuid4().hex}"
        cls.create_resources_and_boto_clients()

    def test_no_events(self):
        function_name = "HelloWorldFunction1"
        # Make sure the state is clean
        TestRemoteTestEvent.delete_all_test_events(function_name)
        self.list_events_and_check(
            self.stack_name,
            function_name,
            expected_output="",
            expected_error="Error: No events found for function HelloWorldFunction1",
        )
        self.get_event_and_check(
            self.stack_name,
            function_name,
            "event1",
            expected_output="",
            expected_error="Error: No events found for function HelloWorldFunction1",
        )

    def test_event_workflow(self):
        function_to_check = "HelloWorldFunction2"
        # Make sure the state is clean
        TestRemoteTestEvent.delete_all_test_events(function_to_check)
        event_contents1 = {"key1": "Hello", "key2": "serverless", "key3": "world"}
        event_contents2 = {"a": "A", "b": "B", "c": "C"}

        # Add one event
        self.put_event_and_check(self.stack_name, function_to_check, "event1", "event_hello.json")
        self.get_event_and_check(self.stack_name, function_to_check, "event1", json.dumps(event_contents1))

        # Check event
        self.list_events_and_check(self.stack_name, function_to_check, "event1")

        # Add another event
        self.put_event_and_check(self.stack_name, function_to_check, "event2", "event_a_b_c.json")
        self.get_event_and_check(self.stack_name, function_to_check, "event2", json.dumps(event_contents2))

        # Check two events
        self.list_events_and_check(self.stack_name, function_to_check, os.linesep.join(["event1", "event2"]))

        # Invoke with two events (function returns the same event that it receives)
        self.remote_invoke_and_check(self.stack_name, function_to_check, "event1", event_contents1)
        self.remote_invoke_and_check(self.stack_name, function_to_check, "event2", event_contents2)

        # Delete the events
        self.delete_event_and_check(self.stack_name, function_to_check, "event1")
        self.delete_event_and_check(self.stack_name, function_to_check, "event2")

    # Helper methods
    def remote_invoke_and_check(self, stack_name, resource_id, test_event_name, expected_output):
        command_list = self.get_remote_invoke_command_list(
            stack_name=stack_name,
            resource_id=resource_id,
            test_event_name=test_event_name,
            output="json",
        )
        remote_invoke_result = run_command(command_list)
        self.assertEqual(0, remote_invoke_result.process.returncode)
        remote_invoke_stdout = json.loads(remote_invoke_result.stdout.strip().decode())
        response_payload = json.loads(remote_invoke_stdout["Payload"])
        self.assertDictEqual(response_payload, expected_output)

    def put_event_and_check(self, stack_name, resource_id, test_event_name, event_file_name):
        event_file_path = str(self.events_folder_path.joinpath(event_file_name))
        command_put = self.get_command_list(
            "put",
            resource_id=resource_id,
            stack_name=stack_name,
            name=test_event_name,
            file=event_file_path,
        )
        put_result = run_command(command_put)
        output_put = put_result.stdout.strip()
        self.assertEqual(output_put.decode("utf-8"), f"Put remote event '{test_event_name}' completed successfully")

    def list_events_and_check(self, stack_name, resource_id, expected_output, expected_error=""):
        command_list = self.get_command_list("list", stack_name=stack_name, resource_id=resource_id)
        list_result = run_command(command_list)
        output = list_result.stdout.strip()
        error_output = list_result.stderr.strip()
        self.assertEqual(output.decode("utf-8"), expected_output)
        if expected_error:
            self.assertIn(expected_error, error_output.decode("utf-8"))

    def delete_event_and_check(self, stack_name, resource_id, test_event_name):
        command_list = self.get_command_list(
            "delete",
            stack_name=stack_name,
            resource_id=resource_id,
            name=test_event_name,
        )
        delete_result = run_command(command_list)
        self.assertEqual(0, delete_result.process.returncode)
        output_delete = delete_result.stdout.strip()
        self.assertEqual(
            output_delete.decode("utf-8"), f"Delete remote event '{test_event_name}' completed successfully"
        )

    def get_event_and_check(self, stack_name, resource_id, event_name, expected_output, expected_error=""):
        command_list = self.get_command_list("get", stack_name=stack_name, resource_id=resource_id, name=event_name)
        list_result = run_command(command_list)
        output = list_result.stdout.strip()
        error_output = list_result.stderr.strip()
        self.assertEqual(output.decode("utf-8"), expected_output)
        if expected_error:
            self.assertIn(expected_error, error_output.decode("utf-8"))
