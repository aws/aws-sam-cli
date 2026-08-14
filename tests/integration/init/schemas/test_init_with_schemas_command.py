import os
import tempfile
import pytest
from functools import lru_cache
from pathlib import Path
from unittest import skipIf

from boto3.session import Session
from click.testing import CliRunner

from samcli.commands.init import cli as init_cmd
from samcli.commands.init.init_templates import InitTemplates
from samcli.commands.init.interactive_init_flow import get_sorted_runtimes
from tests.integration.init.schemas.schemas_test_data_setup import SchemaTestDataSetup
from tests.testing_utils import RUNNING_ON_CI, RUNNING_TEST_FOR_MASTER_ON_CI, RUN_BY_CANARY

# Schemas tests require credentials. This is to skip running the test where credentials are not available.
SKIP_SCHEMA_TESTS = RUNNING_ON_CI and RUNNING_TEST_FOR_MASTER_ON_CI and not RUN_BY_CANARY

EVENT_BRIDGE_USE_CASE = "Infrastructure event management"

# Runtimes these tests init against. None of these tests is about a specific runtime
# version -- they exercise the schemas flows (registry choice, pagination, profiles) --
# so the version is incidental and repeated across tests. Naming it here means a runtime
# leaving the manifest is a one-line change instead of a hunt through the file.
# `python3.9` is already deprecated, so that is not hypothetical.
#
# These are the labels the *prompt* displays, which are not always the runtime id:
# the go entry shows as "go (provided.al2)". `_get_runtime_position` matches them
# against the manifest, and raises with the available list if one disappears.
JAVA_RUNTIME_FOR_INIT = "java17.al2023"
PYTHON_RUNTIME_FOR_INIT = "python3.9"
GO_RUNTIME_FOR_INIT = "go (provided.al2)"


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


@lru_cache(maxsize=1)
def _get_manifest():
    """Fetch the preprocessed app-templates manifest once per test process.

    `get_preprocessed_manifest` is not cheap or deterministic per call:
    `InitTemplates._get_manifest` does `requests.get(MANIFEST_URL, timeout=10)` and, on
    timeout / connection error / non-200, falls back to cloning the templates repo or
    reading the bundled local manifest. Every test below resolves both a use case and a
    runtime, so without caching that is two fetches per test.

    Caching also removes a correctness trap. Resolved independently, one call could
    succeed against MANIFEST_URL while the other fell back to the local manifest --
    giving a use-case position and a runtime position from two different snapshots,
    which is the same answer misalignment these helpers exist to prevent.
    """
    return InitTemplates().get_preprocessed_manifest(None, None, None, None)


def _get_runtime_position(runtime_name):
    """Return the 1-based menu position of a runtime in the `sam init` runtime prompt.

    The prompt lists the runtimes the app-templates manifest offers for
    EVENT_BRIDGE_USE_CASE, ordered by `get_sorted_runtimes`. That ordering shifts
    whenever a runtime is added or removed, so hardcoding a position silently
    starts selecting a different runtime -- every answer after it then lands on
    the wrong question. Resolve it the same way `_get_registry_position` does.
    """
    runtime_options = _get_manifest()[EVENT_BRIDGE_USE_CASE]
    runtimes = get_sorted_runtimes(list(runtime_options.keys()))
    for i, name in enumerate(runtimes, 1):
        if name == runtime_name:
            return i
    raise ValueError(f"Runtime '{runtime_name}' not found. Available: {runtimes}")


def _get_use_case_position(use_case_name):
    """Return the 1-based menu position of a use case in the `sam init` template prompt.

    Same rationale as `_get_runtime_position`: the manifest grows over time, so
    the position of a use case is not stable.
    """
    use_cases = list(_get_manifest().keys())
    for i, name in enumerate(use_cases, 1):
        if name == use_case_name:
            return i
    raise ValueError(f"Use case '{use_case_name}' not found. Available: {use_cases}")


@skipIf(SKIP_SCHEMA_TESTS, "Skip schema test")
@pytest.mark.xdist_group(name="sam_init")
class TestBasicInitWithEventBridgeCommand(SchemaTestDataSetup):
    @pytest.mark.timeout(300)
    def test_init_interactive_with_event_bridge_app_aws_registry(self):
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {java_runtime_pos}: JAVA_RUNTIME_FOR_INIT (dynamic position)
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # 1: select schema from cli_paginator
        # {aws_registry_pos}: select aws.events as registries (dynamic position)
        # 9: select schema AWSAPICallViaCloudTrail
        aws_registry_pos = _get_registry_position("aws.events")
        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(JAVA_RUNTIME_FOR_INIT)}
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
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {java_runtime_pos}: JAVA_RUNTIME_FOR_INIT (dynamic position)
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # {partner_registry_pos}: partner registry (dynamic position)
        # 1: select aws schema
        partner_registry_pos = _get_registry_position("partner-registry")
        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(JAVA_RUNTIME_FOR_INIT)}
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
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {java_runtime_pos}: JAVA_RUNTIME_FOR_INIT (dynamic position)
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # {pagination_registry_pos}: select pagination-registry (dynamic position)
        # N: Go to next page
        # P: Go to previous page
        # 2: select 2nd schema
        pagination_registry_pos = _get_registry_position("test-pagination")
        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(JAVA_RUNTIME_FOR_INIT)}
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
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {java_runtime_pos}: JAVA_RUNTIME_FOR_INIT (dynamic position)
        # 2: Maven
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-maven: response to name
        # Y: Use default aws configuration
        # {other_schema_pos}: select other-schema registry (dynamic position)
        # 1: select 1st schema
        other_schema_pos = _get_registry_position("other-schema")
        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(JAVA_RUNTIME_FOR_INIT)}
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
        # WHEN the user follows interactive init prompts
        # 1: AWS Quick Start Templates
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {python_runtime_pos}: PYTHON_RUNTIME_FOR_INIT (dynamic position)
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-python39: response to name
        # Y: Use default aws configuration
        # 1: select schema from cli_paginator
        # {aws_registry_pos}: select aws.events as registries (dynamic position)
        # 1: select aws schema
        aws_registry_pos = _get_registry_position("aws.events")
        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(PYTHON_RUNTIME_FOR_INIT)}
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
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {go_runtime_pos}: GO_RUNTIME_FOR_INIT (dynamic position)
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-go: response to name
        # Y: Use default aws configuration
        # {aws_registry_pos}: select aws.events as registries (dynamic position)
        # 1: select aws schema
        aws_registry_pos = _get_registry_position("aws.events")
        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(GO_RUNTIME_FOR_INIT)}
2
N
N
N
eb-app-go
Y
{aws_registry_pos}
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
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {python_runtime_pos}: PYTHON_RUNTIME_FOR_INIT (dynamic position)
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
        #
        # The registry answer stays hardcoded here, unlike the sibling tests. This test
        # deliberately drives a non-default profile and an explicit us-east-1, so the
        # registries the prompt lists are those of *that* profile/region --
        # `_get_registry_position` resolves against the default `Session()`, so using it
        # here would look up the wrong account and region.

        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(PYTHON_RUNTIME_FOR_INIT)}
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
        # {use_case_pos}: Infrastructure event management - Use case (dynamic position)
        # {python_runtime_pos}: PYTHON_RUNTIME_FOR_INIT (dynamic position)
        # 2: select event-bridge app from scratch
        # N: disable adding xray tracing
        # N: disable cloudwatch insights
        # N: disable structured logging
        # eb-app-python39: response to name
        # Y: Use default profile
        # 1: select aws.events as registries
        # 1: select aws schema

        user_input = f"""
1
{_get_use_case_position(EVENT_BRIDGE_USE_CASE)}
{_get_runtime_position(PYTHON_RUNTIME_FOR_INIT)}
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
