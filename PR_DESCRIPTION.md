#### Which issue(s) does this change fix?

Fixes #8933

#### Why is this change necessary?

SAM CLI provides an excellent developer experience for Lambda Image functions (`sam build && sam deploy`), but users deploying containerized workloads to ECS (Fargate) or Bedrock AgentCore must manage their Docker build/push/deploy pipeline separately — even when these resources live in the same CloudFormation template. This creates a fragmented workflow requiring external tooling for an identical operation: build image → push to ECR → deploy.

#### How does it address the issue?

Extends the existing Lambda Image build pipeline to recognize `AWS::ECS::TaskDefinition` and `AWS::BedrockAgentCore::Runtime` resources with a `Metadata` block containing `Dockerfile` and `DockerContext`. No new commands — `sam build`, `sam package`, `sam deploy`, and `sam sync` gain awareness of these resource types.

**Template example:**
```yaml
Resources:
  MyAgent:
    Type: AWS::BedrockAgentCore::Runtime
    Metadata:
      Dockerfile: Dockerfile
      DockerContext: ./agent
      Architecture: arm64
    Properties:
      AgentRuntimeArtifact:
        ContainerConfiguration:
          ContainerUri: placeholder

  MyTask:
    Type: AWS::ECS::TaskDefinition
    Metadata:
      Dockerfile: Dockerfile
      DockerContext: ./app
      ContainerName: web
    Properties:
      ContainerDefinitions:
        - Name: web
          Image: placeholder
```

**Key implementation details:**
- Reuses `_build_lambda_image()` — same Docker build logic, buildkit support included
- `--resolve-image-repos` auto-creates ECR repos via companion stack
- `ContainerName` metadata targets specific containers in multi-container TaskDefinitions
- `Architecture` metadata sets `--platform` (e.g., `arm64` for AgentCore)
- `ARTIFACT_TYPE = ZIP` to pass the `PackageType` filter (these resources don't have `PackageType`)
- No SAM Transform changes needed — uses native CloudFormation resource types

**Design document:** `designs/container_image_builds_ecs_agentcore.md`

#### What side effects does this change have?

- `sam build` logs "Found N container service resource(s) to build" when applicable resources are present. No behavior change for templates without these resources.
- `--resolve-image-repos` creates ECR repos for ECS/AgentCore in addition to Lambda Image functions.
- `_update_built_resource` adds an optional `metadata` parameter (backward compatible, defaults to `None`).

#### Mandatory Checklist
**PRs will only be reviewed after checklist is complete**

- [x] Review the [generative AI contribution guidelines](https://github.com/aws/aws-sam-cli/blob/develop/CONTRIBUTING.md#ai-usage)
- [x] Add input/output [type hints](https://docs.python.org/3/library/typing.html) to new functions/methods
- [x] Write design document if needed ([Do I need to write a design document?](https://github.com/aws/aws-sam-cli/blob/develop/DEVELOPMENT_GUIDE.md#design-document))
- [x] Write/update unit tests
- [x] Write/update integration tests
- [x] Write/update functional tests if needed
- [x] `make pr` passes
- [x] `make update-reproducible-reqs` if dependencies were changed
- [ ] Write documentation

By submitting this pull request, I confirm that my contribution is made under the terms of the [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0).
