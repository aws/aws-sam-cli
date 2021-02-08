import os
import tempfile
from unittest import skipIf

from click.testing import CliRunner
from samcli.commands.init import cli as init_cmd
from pathlib import Path

from samcli.lib.utils.packagetype import ZIP
from tests.integration.init.schemas.schemas_test_data_setup import SchemaTestDataSetup
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Schemas tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SCHEMA_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY


@skipIf(SKIP_SCHEMA_TESTS, "Skip schema test")
class TestBasicInitWithEventBridgeCommand(SchemaTestDataSetup):
    def test_init_interactive_with_event_bridge_app_aws_registry(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Zip Packagetype
        # 14: Java runtime
        # 1: dependency manager maven
        # eb-app-maven: response to name
        # 3: select event-bridge app from scratch
        # Y: Use default profile
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
1
14
1
eb-app-maven
3
Y
1
1
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

    def test_init_interactive_with_event_bridge_app_partner_registry(self):
        # setup schema data
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Zip Packagetype
        # 14: Java runtime
        # 1: dependency manager maven
        # eb-app-maven: response to name
        # 3: select event-bridge app from scratch
        # Y: Use default profile
        # 3: partner registry
        # 1: select aws schema

        user_input = """
1
1
14
1
eb-app-maven
3
Y
3
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

    def test_init_interactive_with_event_bridge_app_pagination(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Zip Packagetype
        # 14: Java Runtime
        # 1: dependency manager maven
        # eb-app-maven: response to name
        # 3: select event-bridge app from scratch
        # Y: Use default profile
        # 4: select pagination-registry as registries
        # N: Go to next page
        # P Go to previous page
        # select 2nd schema

        user_input = """
1
1
14
1
eb-app-maven
3
Y
4
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

    def test_init_interactive_with_event_bridge_app_customer_registry(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Zip Packagetype
        # 14: Java Runtime
        # 1: dependency manager maven
        # eb-app-maven: response to name
        # 3: select event-bridge app from scratch
        # Y: Use default profile
        # 2: select 2p-schema other-schema
        # 1: select 1 schema

        user_input = """
1
1
14
1
eb-app-maven
3
Y
2
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

    def test_init_interactive_with_event_bridge_app_aws_schemas_python(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Zip Packagetype
        # 9: Python 3.7
        # eb-app-python37: response to name
        # 3: select event-bridge app from scratch
        # Y: Use default profile
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
1
9
eb-app-python37
3
Y
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)

            self.assertFalse(result.exception)
            expected_output_folder = Path(temp, "eb-app-python37")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world_function", "schema").is_dir())

    def test_init_interactive_with_event_bridge_app_non_default_profile_selection(self):
        self._init_custom_config("mynewprofile", "us-west-2")
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Zip Packagetype
        # 9: Python 3.7
        # eb-app-python37: response to name
        # 3: select event-bridge app from scratch
        # N: Use default profile
        # 2: uses second profile from displayed one (myprofile)
        # schemas aws region us-east-1
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
1
9
eb-app-python37
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
            expected_output_folder = Path(temp, "eb-app-python37")
            self.assertTrue(expected_output_folder.exists)
            self.assertTrue(expected_output_folder.is_dir())
            self.assertTrue(Path(expected_output_folder, "hello_world_function", "schema").is_dir())

            self._tear_down_custom_config()

    def test_init_interactive_with_event_bridge_app_non_supported_schemas_region(self):
        self._init_custom_config("default", "cn-north-1")
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # 1: Zip Pacakgetype
        # 9: Python 3.7
        # eb-app-python37: response to name
        # 3: select event-bridge app from scratch
        # Y: Use default profile
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = """
1
1
9
eb-app-python37
3
Y
1
1
        """
        with tempfile.TemporaryDirectory() as temp:
            runner = CliRunner()
            result = runner.invoke(init_cmd, ["--output-dir", temp], input=user_input)
            self.assertTrue(result.exception)
            self._tear_down_custom_config()


def _get_command():
    command = "sam"
    if os.getenv("SAM_CLI_DEV"):
        command = "samdev"
    return command
