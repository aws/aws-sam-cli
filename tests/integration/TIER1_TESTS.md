# Tier 1: Cross-Platform Smoke Tests

These tests are marked with `@pytest.mark.tier1` and run on every OS/container-runtime
combination (Linux+Docker, Linux+Finch, Windows+Docker, etc.). They exercise critical
platform-specific code paths while remaining fast.

Run with: `pytest -m tier1`

## Selection Criteria

- File system operations (path separators, symlinks, build artifacts)
- Container runtime interaction (Docker API, image pulling, container lifecycle)
- Process spawning (build subprocesses, local invoke bootstrapping)
- Network operations (HTTP server, port binding)
- At least one test per SAM CLI command
- At least one build test per major runtime category
- Coverage of every major feature area (layers, sync, deploy, terraform, durable, regression)

## Selected Tests

### Build Tests (per runtime)

| Runtime | Test Class | File | Key Coverage |
|---------|-----------|------|-------------|
| Python | `TestBuildCommand_PythonFunctions_WithDocker` | test_build_cmd_python.py | Container build, pip install, requirements.txt |
| Java | `TestBuildCommand_Java` | test_build_cmd_java.py | Maven/Gradle in container, JAR creation |
| Node.js | `TestBuildCommand_EsbuildFunctions` | test_build_cmd_node.py | Esbuild bundling, sourcemaps |
| .NET | `TestBuildCommand_Dotnet_cli_package` | test_build_cmd_dotnet.py | dotnet CLI, NuGet restore |
| Ruby | `TestBuildCommand_RubyFunctions` | test_build_cmd.py | Bundler, Gemfile handling |
| Rust | `TestBuildCommand_Rust` | test_build_cmd_rust.py | cargo-lambda, binary compilation |
| Provided | `TestBuildCommand_ProvidedFunctions` | test_build_cmd_provided.py | Makefile builds, custom runtimes |

### Build Tests (general)

| Test Class | File | Key Coverage |
|-----------|------|-------------|
| `TestBuildWithNestedStacks` | test_build_cmd.py | Nested templates, path handling, artifact dedup |
| `TestSamConfigWithBuild` | test_build_samconfig.py | Config file parsing (.toml/.yaml/.json) |

### Terraform Build Tests

| Test Class | File | Key Coverage |
|-----------|------|-------------|
| `TestBuildTerraformApplicationsWithZipBasedLambdaFunctionAndLocalBackend` | test_build_terraform_applications.py | Terraform hook, local backend, zip builds |

### Local Command Tests

| Command | Test Class | File | Key Coverage |
|---------|-----------|------|-------------|
| `local invoke` | `TestSamPythonHelloWorldIntegration` | test_integrations_cli.py | Container lifecycle, function invocation, env vars |
| `local invoke` (layers) | `TestLocalZipLayerVersion` | test_integrations_cli.py | Local zip layer resolution |
| `local invoke` (durable) | `TestInvokeDurable` | test_invoke_durable.py | Durable function execution, callbacks, state |
| `local start-api` | `TestService` | test_start_api.py | HTTP server, port binding, API Gateway emulation |
| `local start-lambda` | `TestLambdaService` | test_start_lambda.py | Lambda service emulation, boto3 SDK compat |
| `local generate-event` | `Test_EventGeneration_Integ` | test_cli_integ.py | CLI invocation, JSON output |
| `local callback` | `TestLocalCallback` | test_callback.py | Durable callback CLI commands |
| `local execution` | `TestLocalExecution` | test_execution.py | Durable execution CLI commands |

### Cloud Command Tests

| Command | Test Class | File | Key Coverage |
|---------|-----------|------|-------------|
| `sam init` | `TestBasicInitCommand` | test_init_command.py | Template scaffolding, directory creation |
| `sam validate` | `TestValidate` | test_validate_command.py | Template validation, cfn-lint |
| `sam deploy` | `TestDeploy` | test_deploy_command.py | CloudFormation stack deploy, changeset |
| `sam sync` | `TestSyncInfra` | test_sync_infra.py | Infrastructure sync, stack updates |

### Regression Tests

| Test Class | File | Key Coverage |
|-----------|------|-------------|
| `TestPackageRegression` | test_package_regression.py | Package backward compatibility |
