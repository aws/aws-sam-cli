# Integration Test Cloud vs Local Analysis

This report classifies each integration test file by whether it requires AWS cloud
interaction or runs entirely locally. "Cloud" means the test uses boto3 or AWS CLI
to interact with real AWS services (S3, ECR, CloudFormation, Lambda, etc.).
"Local" means the test only uses local processes (sam build, sam local invoke,
Docker containers, HTTP to localhost).

## Summary

| Job | Local | Cloud | Mixed | Total |
|-----|-------|-------|-------|-------|
| Build (all 4 jobs) | 10 | 0 | 0 | 10 |
| terraform-build | 2 | 3 | 0 | 5 |
| package-delete-deploy | 0 | 5 | 0 | 5 |
| sync | 0 | 5 | 0 | 5 |
| local-invoke | 5 | 1 | 1 | 7 |
| local-start1 | 6 | 0 | 0 | 6 |
| local-start2 | 5 | 0 | 0 | 5 |
| other-and-e2e | 12 | 14 | 1 | 27 |
| **Total** | **40** | **28** | **2** | **70** |

~57% local-only, ~40% cloud-required, ~3% mixed.

---

## build-x86 / build-arm64 / build-x86-container / build-arm64-container

All build tests run `sam build` with local Docker containers. No AWS service calls.

| File | Type | Reason |
|------|------|--------|
| test_build_cmd.py | Local | sam build + local Docker, no AWS calls |
| test_build_cmd_arm64.py | Local | ARM64 builds, local Docker only |
| test_build_cmd_dotnet.py | Local | .NET builds, local only |
| test_build_cmd_java.py | Local | Java Gradle/Maven builds, local only |
| test_build_cmd_node.py | Local | Node.js esbuild/npm, local only |
| test_build_cmd_provided.py | Local | Custom runtime Makefile builds, local only |
| test_build_cmd_python.py | Local | Python builds, local Docker only |
| test_build_cmd_rust.py | Local | Rust cargo-lambda builds, local only |
| test_build_in_source.py | Local | Build-in-source feature, local filesystem |
| test_build_samconfig.py | Local | Config file handling, local only |

---

## terraform-build

| File | Type | Reason |
|------|------|--------|
| test_build_terraform_applications.py | Cloud | boto3 S3 for Terraform backend state buckets |
| test_build_terraform_applications_other_cases.py | Local | Error cases and invalid options, no AWS calls |
| test_invoke_terraform_applications.py | Cloud | Creates Lambda layers and S3 buckets via boto3 |
| test_start_api_with_terraform_application.py | Local | HTTP requests to localhost only |
| test_start_lambda_terraform_applications.py | Cloud | Creates Lambda layers and S3 buckets via boto3 |

---

## package-delete-deploy

100% cloud. All tests deploy to or clean up real AWS resources.

| File | Type | Reason |
|------|------|--------|
| test_package_command_image.py | Cloud | Pushes images to ECR, uploads to S3 |
| test_package_command_zip.py | Cloud | Uploads artifacts to S3, KMS encryption |
| test_delete_command.py | Cloud | Deletes CloudFormation stacks, S3, ECR cleanup |
| test_deploy_command.py | Cloud | Creates/updates CloudFormation stacks, S3, ECR |
| test_managed_stack_deploy.py | Cloud | Manages CloudFormation stacks and S3 buckets |

---

## sync

100% cloud. All tests run `sam sync` which deploys to AWS.

| File | Type | Reason |
|------|------|--------|
| test_sync_adl.py | Cloud | Deploys via sam sync, invokes real Lambda |
| test_sync_build_in_source.py | Cloud | Deploys to CloudFormation, invokes Lambda |
| test_sync_code.py | Cloud | boto3 CloudFormation/ECR/Lambda/API GW/Step Functions |
| test_sync_infra.py | Cloud | Deploys infra changes, Lambda, API GW, Step Functions |
| test_sync_watch.py | Cloud | Continuous deploy to CloudFormation |

---

## local-invoke

| File | Type | Reason |
|------|------|--------|
| test_integration_cli_images.py | Local | Docker image builds + local invoke |
| test_integrations_cli.py | Mixed | Most tests local; Layer tests use boto3 publish_layer_version |
| test_integrations_do_cli.py | Local | Non-UTF8 encoding test, local only |
| test_invoke_build_in_source.py | Local | Build-in-source + local invoke |
| test_invoke_cdk_templates_with_function_id.py | Local | CDK templates, local invoke |
| test_invoke_durable.py | Local | Durable functions, local only |
| test_with_credentials.py | Cloud | Function code calls STS GetCallerIdentity |

---

## local-start1 (start_api)

100% local. All tests make HTTP requests to localhost.

| File | Type | Reason |
|------|------|--------|
| test_start_api.py | Local | HTTP to 127.0.0.1, Docker containers |
| test_start_api_cdk_template.py | Local | CDK templates, HTTP to localhost |
| test_start_api_durable.py | Local | Durable functions, HTTP to localhost |
| lambda_authorizers/test_cfn_authorizer_definitions.py | Local | Authorizers in local Docker |
| lambda_authorizers/test_sfn_props_lambda_authorizers.py | Local | SAM authorizers, local only |
| lambda_authorizers/test_swagger_authorizer_definitions.py | Local | Swagger authorizers, local only |

---

## local-start2 (start_lambda, callback, execution)

100% local. boto3 clients point to local endpoint (127.0.0.1) with unsigned requests.

| File | Type | Reason |
|------|------|--------|
| test_start_lambda.py | Local | boto3 with local endpoint, unsigned |
| test_start_lambda_cdk.py | Local | boto3 with local endpoint, CDK templates |
| test_start_lambda_durable.py | Local | Durable functions, local endpoint |
| test_callback.py | Local | sam local callback CLI, local only |
| test_execution.py | Local | sam local execution CLI, local only |

---

## other-and-e2e

| File | Type | Reason |
|------|------|--------|
| docs/test_docs_command.py | Local | CLI help docs |
| init/test_init_command.py | Local | sam init from templates |
| init/test_init_with_schemas_command.py | Cloud | EventBridge Schema Registry |
| list/test_endpoints_command.py | Cloud | CloudFormation stack queries |
| list/test_resources_command.py | Cloud | CloudFormation stack queries |
| list/test_stack_outputs_command.py | Cloud | CloudFormation stack queries |
| logs/test_logs_command.py | Cloud | Lambda, Step Functions, CloudWatch |
| pipeline/test_bootstrap_command.py | Cloud | CloudFormation, IAM, S3, ECR |
| pipeline/test_init_command.py | Mixed | TestInit local; TestInitWithBootstrap cloud |
| publish/test_command_integ.py | Cloud | Serverless Application Repository |
| remote/invoke/test_remote_invoke.py | Cloud | Lambda, SQS, Kinesis, Step Functions |
| remote/invoke/test_lambda_invoke_response_stream.py | Cloud | Lambda response streaming |
| remote/test_event/test_remote_test_event.py | Cloud | EventBridge, Lambda test events |
| remote/ (6 stub files) | Local | Empty pass stubs, no implementation |
| root/test_root_command.py | Local | CLI help/version/info |
| telemetry/test_experimental_metric.py | Local | Local mock server |
| telemetry/test_installed_metric.py | Local | Local mock server |
| telemetry/test_prompt.py | Local | Prompt display |
| telemetry/test_telemetry_contract.py | Local | Local mock server |
| traces/test_traces_command.py | Cloud | X-Ray, Lambda, Step Functions |
| validate/test_validate_command.py | Cloud | Template validation against AWS |
| end_to_end/test_runtimes_e2e.py | Cloud | Full deploy + remote invoke |
| end_to_end/test_stages.py | Cloud | S3, CloudFormation |
| regression/deploy/test_deploy_regression.py | Cloud | CloudFormation, SNS, KMS |
| regression/package/test_package_regression.py | Cloud | S3 uploads |
