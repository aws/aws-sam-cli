# Tier 1: Cross-Platform Smoke Tests

These tests are marked with `@pytest.mark.tier1` and run on every OS/container-runtime
combination (Linux+Docker, Linux+Finch, Windows+Docker, etc.).

Run with: `pytest -m tier1 tests/integration tests/regression`

## Build Tests (per runtime — non-container + container)

| Runtime | Non-container Test | Container Test | File |
|---------|-------------------|----------------|------|
| Python | `test_tier1_python_build` | `test_tier1_python_build_in_container` | test_build_cmd_python.py |
| Java | `test_tier1_java_build` | `test_tier1_java_build_in_container` | test_build_cmd_java.py |
| Node.js | `test_tier1_node_build` | `test_tier1_node_build_in_container` | test_build_cmd_node.py |
| .NET | `test_tier1_dotnet_build` | `test_tier1_dotnet_build_in_container` | test_build_cmd_dotnet.py |
| Ruby | `test_building_ruby_3_2_0` | `test_building_ruby_3_2_1_in_container` | test_build_cmd.py |
| Rust | `test_tier1_rust_build` | `test_tier1_rust_build_in_container` | test_build_cmd_rust.py |
| Provided | `test_tier1_provided_build` | `test_tier1_provided_build_in_container` | test_build_cmd_provided.py |

## Build Tests (general)

| Test | File | Coverage |
|------|------|----------|
| `test_nested_build_invoke_in_container` | test_build_cmd.py | Nested templates, path handling |
| `test_samconfig_parameters_are_overridden` | test_build_samconfig.py | Config file parsing |
| `test_build_and_invoke_lambda_functions` | test_build_terraform_applications.py | Terraform hook builds |

## Local Command Tests

| Command | Test | File | Coverage |
|---------|------|------|----------|
| `local invoke` | `test_invoke_returncode_is_zero` | test_integrations_cli.py | Container lifecycle, invocation |
| `local invoke` (layers) | `test_local_zip_layers` | test_integrations_cli.py | Local zip layer resolution |
| `local invoke` (durable) | `test_tier1_durable_invoke` | test_invoke_durable.py | Durable function execution |
| `local start-api` | `test_calling_proxy_endpoint` | test_start_api.py | HTTP server, API Gateway |
| `local start-lambda` | `test_invoke_with_data` | test_start_lambda.py | Lambda service emulation |
| `local generate-event` | `test_generate_event_substitution` | test_cli_integ.py | CLI event generation |
| `local callback` | `test_tier1_callback` | test_callback.py | Durable callback CLI |
| `local execution` | `test_tier1_execution` | test_execution.py | Durable execution CLI |

## Other SAM CLI Commands

| Command | Test | File | Coverage |
|---------|------|------|----------|
| `sam init` | `test_init_command_passes_and_dir_created` | test_init_command.py | Template scaffolding |
| `sam validate` | `test_default_template_file_choice` | test_validate_command.py | Template validation |
| `sam deploy` | `test_deploy_guided_zip` | test_deploy_command.py | CloudFormation deploy |
| `sam sync` | `test_tier1_sync_infra` | test_sync_infra.py | Infrastructure sync |
| `sam delete` | `test_tier1_delete` | test_delete_command.py | Stack deletion, S3 cleanup |
| `sam package` | `test_tier1_package` | test_package_command_zip.py | S3 artifact upload |

## Build Tests (special)

| Test | File | Coverage |
|------|------|----------|
| `TestBuildWithNestedStacks3LevelWithSymlink` | test_build_cmd.py | Symlink resolution in nested stacks |
| `test_tier1_layer_build` | test_build_cmd.py | Layer build with Makefile |

## ARM64 Build Tests

| Runtime | Test | File |
|---------|------|------|
| Python | `test_tier1_python_arm64_build` | test_build_cmd_arm64.py |
| Java | `test_tier1_java_arm64_build` | test_build_cmd_arm64.py |
| Node.js | `test_tier1_node_arm64_build` | test_build_cmd_arm64.py |
| Ruby | `test_tier1_ruby_arm64_build` | test_build_cmd_arm64.py |
| Provided | `test_tier1_provided_arm64_build` | test_build_cmd_arm64.py |
| Rust | `test_tier1_rust_arm64_build` | test_build_cmd_arm64.py |
