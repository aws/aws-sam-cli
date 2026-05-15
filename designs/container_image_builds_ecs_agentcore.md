Container Image Builds for ECS and AgentCore
=============================================

This is the design for extending `sam build`, `sam package`, `sam deploy`, and `sam sync`
to support building and deploying container images for non-Lambda resources:
`AWS::ECS::TaskDefinition` and `AWS::BedrockAgentCore::Runtime`.

What is the problem?
--------------------

SAM CLI provides an excellent developer experience for Lambda Image functions: a single
`sam build && sam deploy` builds the Docker image, pushes to ECR, and deploys via
CloudFormation. However, users deploying containerized workloads to ECS (Fargate) or
Bedrock AgentCore must manage their Docker build/push/deploy pipeline separately, even
when these resources live in the same CloudFormation template alongside Lambda functions.

This creates a fragmented workflow where developers need external tooling (shell scripts,
Makefiles, or CI/CD steps) for the identical operation: build image → push to ECR →
update template with ECR URI → deploy.

What will be changed?
---------------------

We extend the existing Lambda Image build pipeline to recognize `AWS::ECS::TaskDefinition`
and `AWS::BedrockAgentCore::Runtime` resources that have a `Metadata` block with
`Dockerfile` and `DockerContext`. No new commands are introduced — the existing
`sam build`, `sam package`, `sam deploy`, and `sam sync` gain awareness of these
resource types.

### Design Principles

1. **Same convention** — Uses the identical Metadata block as Lambda Image functions
   (Dockerfile, DockerContext, DockerTag, DockerBuildArgs, DockerBuildTarget)
2. **No Transform changes** — Works with native CloudFormation resource types
3. **Opt-in** — Only resources with the Metadata block are affected; existing templates
   work unchanged
4. **Reuse** — Delegates to the same `_build_lambda_image()` Docker build logic

Success criteria for the change
-------------------------------

1. `sam build` discovers and builds container images for ECS TaskDefinitions and
   AgentCore Runtimes that have Dockerfile metadata
2. `sam deploy --resolve-image-repos` auto-creates ECR repos for these resources
3. `sam package` / `sam deploy` pushes images to ECR and rewrites the template with
   the ECR URI at the correct property path
4. `sam sync` builds, pushes, and triggers redeployment for these resources
5. Multi-container ECS TaskDefinitions can target a specific container via `ContainerName`
6. Architecture can be specified via `Architecture` metadata (e.g., `arm64`)
7. Buildkit support works automatically (shared with Lambda Image builds)
8. No regressions for existing Lambda, Layer, or API builds

User Experience
---------------

### Template Format

```yaml
Resources:
  # AgentCore Runtime
  MyAgent:
    Type: AWS::BedrockAgentCore::Runtime
    Metadata:
      Dockerfile: Dockerfile
      DockerContext: ./agent
      DockerTag: latest
      Architecture: arm64
    Properties:
      AgentRuntimeName: my_agent
      AgentRuntimeArtifact:
        ContainerConfiguration:
          ContainerUri: placeholder
      NetworkConfiguration:
        NetworkMode: PUBLIC
      RoleArn: !GetAtt AgentRole.Arn

  # ECS TaskDefinition (multi-container)
  MyTask:
    Type: AWS::ECS::TaskDefinition
    Metadata:
      Dockerfile: Dockerfile
      DockerContext: ./app
      DockerTag: latest
      ContainerName: web
    Properties:
      Family: my-app
      ContainerDefinitions:
        - Name: envoy
          Image: public.ecr.aws/envoy:latest
        - Name: web
          Image: placeholder
```

### CLI Usage

```bash
# Build container images
sam build

# Deploy with auto ECR repo creation
sam deploy --resolve-image-repos

# Or with explicit repo
sam deploy --image-repositories SimpleAgent=123456789012.dkr.ecr.us-east-1.amazonaws.com/repo

# Live sync
sam sync --stack-name my-stack --watch --resolve-image-repos
```

### Metadata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `Dockerfile` | Yes | Path to Dockerfile relative to DockerContext |
| `DockerContext` | Yes | Build context directory relative to template |
| `DockerTag` | No | Image tag (default: `latest`) |
| `DockerBuildArgs` | No | Dict of build args |
| `DockerBuildTarget` | No | Multi-stage build target |
| `DockerBuildExtraParams` | No | List of extra docker build params |
| `Architecture` | No | Target platform: `x86_64` (default) or `arm64` |
| `ContainerName` | No | ECS only: target container in multi-container TaskDefinition |

Implementation
--------------

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ sam build                                                        │
├─────────────────────────────────────────────────────────────────┤
│ BuildContext.run()                                               │
│   ├── builder.build()          → Lambda functions + layers       │
│   └── _build_container_images() → ECS + AgentCore containers    │
│         ├── SamContainerServiceProvider (discovery)              │
│         ├── ContainerBuildDefinition (build graph)               │
│         └── ApplicationBuilder.build_container_images()          │
│               └── _build_lambda_image() (shared Docker logic)   │
├─────────────────────────────────────────────────────────────────┤
│ sam package / sam deploy                                         │
│   ├── sync_ecr_stack() → auto-creates ECR repos (companion)     │
│   ├── ECSTaskDefinitionImageResource.export() → push + rewrite  │
│   └── AgentCoreRuntimeImageResource.export() → push + rewrite   │
├─────────────────────────────────────────────────────────────────┤
│ sam sync                                                         │
│   └── ECSContainerSyncFlow                                      │
│         ├── gather_resources() → build image                    │
│         ├── sync() → push to ECR + force ECS deployment         │
│         └── SyncFlowFactory (registered for both types)         │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

**`samcli/lib/providers/sam_container_provider.py`** (new)
- `SamContainerServiceProvider`: Scans stacks for ECS/AgentCore resources with
  Dockerfile+DockerContext metadata. Returns `ContainerService` NamedTuples.

**`samcli/lib/build/build_graph.py`** (modified)
- `ContainerBuildDefinition`: Parallel to `FunctionBuildDefinition`. Holds resource
  identifier, type, metadata, and architecture. Reads `Architecture` from metadata.

**`samcli/lib/build/app_builder.py`** (modified)
- `build_container_images()`: Iterates container definitions and builds each.
- `_build_container_image()`: Delegates to `_build_lambda_image()` — same Docker logic.
- `_update_built_resource()`: Extended for ECS (`ContainerDefinitions[N].Image`) and
  AgentCore (`AgentRuntimeArtifact.ContainerConfiguration.ContainerUri`). Accepts
  optional `metadata` param for `ContainerName` targeting.

**`samcli/lib/package/packageable_resources.py`** (modified)
- `ECSTaskDefinitionImageResource`: Custom export for nested `ContainerDefinitions[0].Image`.
- `AgentCoreRuntimeImageResource`: Export using jmespath for deeply nested property path.
- Both use `ARTIFACT_TYPE = ZIP` to pass the `PackageType` filter (these resources
  don't have a `PackageType` property).

**`samcli/lib/sync/flows/ecs_container_sync_flow.py`** (new)
- `ECSContainerSyncFlow`: Builds image, pushes to ECR, forces ECS service redeployment
  by finding services using the task definition family.

**`samcli/lib/bootstrap/companion_stack/companion_stack_manager.py`** (modified)
- `sync_ecr_stack()`: Extended to include container service resources when creating
  ECR repos via the companion stack.

### Property Path Mapping

| Resource Type | Property Path for Image URI |
|---------------|----------------------------|
| `AWS::Serverless::Function` | `ImageUri` |
| `AWS::Lambda::Function` | `Code.ImageUri` |
| `AWS::ECS::TaskDefinition` | `ContainerDefinitions[N].Image` |
| `AWS::BedrockAgentCore::Runtime` | `AgentRuntimeArtifact.ContainerConfiguration.ContainerUri` |

Alternatives Considered
-----------------------

### 1. New SAM Transform resource type (e.g., `AWS::Serverless::ContainerService`)

**Rejected because:**
- Requires changes to the SAM Transform (separate repo, separate approval process)
- Adds coupling between SAM CLI and the Transform
- Users would need to wait for Transform support in all regions
- Native CFN types already work and are well-understood

### 2. Separate `sam container build` command

**Rejected because:**
- Fragments the workflow — users would need to remember different commands
- Doesn't integrate with `sam deploy` and `sam sync` naturally
- The existing `sam build` already handles image builds for Lambda

### 3. Using `PackageType: Image` on ECS/AgentCore resources

**Rejected because:**
- `PackageType` is a Lambda-specific concept not present on ECS or AgentCore resources
- Would require CloudFormation schema changes
- The Metadata-based approach is already the established pattern

Breaking Changes
----------------

None. This is purely additive:
- Templates without ECS/AgentCore Metadata are unaffected
- The `_update_built_resource` signature change is backward compatible (optional param)
- No existing CLI flags or behaviors change

Future Extensions
-----------------

1. **Multiple Dockerfiles per ECS TaskDefinition** — Build multiple containers from
   one resource using a list of Metadata entries
2. **`sam local start-ecs`** — Local testing of ECS containers (similar to `sam local start-api`)
3. **Health check integration** — Wait for container health before marking sync complete
4. **Build caching** — Layer-aware caching for container builds (currently rebuilds fully)
5. **`sam init` templates** — Starter templates for ECS+SAM and AgentCore+SAM projects
