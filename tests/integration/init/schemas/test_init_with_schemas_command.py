import os
import tempfile
import pytest
from pathlib import Path
from unittest import skipIf

from boto3.session import Session
from click.testing import CliRunner

from samcli.commands.init import cli as init_cmd
from tests.integration.init.schemas.schemas_test_data_setup import SchemaTestDataSetup
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Schemas tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SCHEMA_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


def _get_registry_position(registry_name):
    """Query EventBridge Schema registries and return the 1-based menu position for the given registry name.

    The sam init interactive prompt lists registries in alphabetical order.
    This avoids hardcoding positions that break when new registries are added to the account.
    """
    session = Session()
    client = session.client("schemas", region_name=session.region_name)
    paginator = client.get_paginator("list_registries")
    registries = []
    for page in paginator.paginate():
        registries.extend(r["RegistryName"] for r in page["Registries"])
    registries.sort()
    for i, name in enumerate(registries, 1):
        if name == registry_name:
            return i
    raise ValueError(f"Registry '{registry_name}' not found. Available: {registries}")


@skipIf(SKIP_SCHEMA_TESTS, "Skip schema test")
@pytest.mark.xdist_group(name="sam_init")
class TestBasicInitWithEventBridgeCommand(SchemaTestDataSetup):
    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_aws_registry(self):
        aws_registry_pos = _get_registry_position("aws.events")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
1
{aws_registry_pos}
9
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp, "--debug"], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_partner_registry(self):
        partner_registry_pos = _get_registry_position("partner-registry")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
{partner_registry_pos}
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )
            self.assertTrue(
                Path(
                    expected_output_folder,
                    "HelloWorldFunction",
                    "src",
                    "main",
                    "java",
                    "schema",
                    "schema_test_0",
                    "TicketCreated.java",
                ).is_file()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_pagination(self):
        pagination_registry_pos = _get_registry_position("test-pagination")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
{pagination_registry_pos}
N
P
2
        """

        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_customer_registry(self):
        other_schema_pos = _get_registry_position("other-schema")
        user_input = f"""
1
8
4
2
2
N
N
N
eb-app-maven
Y
{other_schema_pos}
1
                """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-maven")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(
                Path(expected_output_folder, "HelloWorldFunction", "src", "main", "java", "schema").is_dir()
            )
            self.assertTrue(
                Path(
                    expected_output_folder,
                    "HelloWorldFunction",
                    "src",
                    "main",
                    "java",
                    "schema",
                    "schema_test_0",
                    "Some_Awesome_Schema.java",
                ).is_file()
            )

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_aws_schemas_python(self):
        aws_registry_pos = _get_registry_position("aws.events")
        user_input = f"""
1
8
8
2
N
N
N
eb-app-python39
Y
1
{aws_registry_pos}
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-python39")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world_function", "schema").is_dir())

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_aws_schemas_go(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 1: Go 1.x
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-go: response to name
        # Y: Use default aws configuration
        # 4: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
8
1
2
N
N
N
eb-app-go
Y
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-go")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "HelloWorld", "schema").is_dir())

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_non_default_profile_selection(self):
        self._init_custom_config("mynewprofile", "us-west-2")
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 8: Python 3.9
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-python38: response to name
        # N: Use default profile
        # 2: uses second profile from displayed one (myprofile)
        # schemas aws region us-east-1
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
8
8
2
N
N
N
eb-app-python39
3
N
2
us-east-1
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-python39")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world_function", "schema").is_dir())

    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_non_supported_schemas_region(self):
        self._init_custom_config("default", "cn-north-1")
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 8: Infrastructure event management - Use case
        # 7: Python 3.9
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-python39: response to name
        # Y: Use default profile
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
8
8
2
N
N
N
eb-app-python39
Y
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)
            self.assertTrue(result.exception)
