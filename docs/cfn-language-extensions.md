# CloudFormation Language Extensions Support

SAM CLI now supports templates that use the `AWS::LanguageExtensions` transform, including `Fn::ForEach`, `Fn::Length`, `Fn::ToJsonString`, and `Fn::FindInMap` with `DefaultValue`.

## How it works

When SAM CLI detects `AWS::LanguageExtensions` in a template's `Transform` section *and* the customer has opted in to local processing, it expands language extension constructs locally before running SAM transforms. This enables `sam build`, `sam package`, `sam deploy`, `sam sync`, `sam validate`, `sam local invoke`, `sam local start-api`, and `sam local start-lambda` to work with templates that use these constructs.

**Local processing is off by default.** When off, SAM CLI passes the template through unchanged; CloudFormation processes the `AWS::LanguageExtensions` transform server-side at deploy time (the pre-1.160.0 behavior).

The expansion happens in two phases when enabled:

1. **Phase 1 (Language Extensions)** — `Fn::ForEach` loops are expanded, intrinsic functions are resolved where possible, and the template is converted to standard CloudFormation.
2. **Phase 2 (SAM Transform)** — The expanded template is processed by the SAM Translator as usual.

The original template (with `Fn::ForEach` intact) is preserved for CloudFormation deployment, since CloudFormation processes the `AWS::LanguageExtensions` transform server-side.

## Enabling Language Extensions

Local processing of `AWS::LanguageExtensions` is opt-in per command. Three activation methods, in priority order (highest first):

1. **CLI flag** — pass `--language-extensions` on a single invocation:

   ```bash
   sam build --language-extensions
   sam package --language-extensions ...
   sam deploy --language-extensions ...
   ```

   `--no-language-extensions` explicitly disables, overriding both samconfig.toml and the env var below.

2. **`samconfig.toml`** — persist the choice per project:

   ```toml
   [default.build.parameters]
   language_extensions = true

   [default.package.parameters]
   language_extensions = true

   [default.deploy.parameters]
   language_extensions = true

   [default.sync.parameters]
   language_extensions = true

   [default.local_invoke.parameters]
   language_extensions = true

   [default.local_start_api.parameters]
   language_extensions = true

   [default.local_start_lambda.parameters]
   language_extensions = true

   [default.validate.parameters]
   language_extensions = true
   ```

   A `samconfig.toml` entry is loaded into Click's defaults, so it takes effect as if the flag were passed — and therefore wins over the env var.

3. **Environment variable** — set `SAM_CLI_ENABLE_LANGUAGE_EXTENSIONS=1` to enable for the current shell:

   ```bash
   export SAM_CLI_ENABLE_LANGUAGE_EXTENSIONS=1
   sam build
   sam local invoke MyFunction
   ```

   Truthy values (case-insensitive): `1`, `true`, `yes`. Anything else, including empty string, is off. The env var is consulted only when neither the CLI flag nor samconfig.toml sets a value.

**Each command needs its own activation.** Passing `--language-extensions` to `sam build` does not propagate to a later `sam local invoke` — local processing is decided per command invocation. Use the env var or samconfig entry to enable across commands without repeating the flag.

## Fn::ForEach

`Fn::ForEach` generates multiple resources, conditions, or outputs from a single template definition:

```yaml
Transform: AWS::LanguageExtensions

Parameters:
  ServiceNames:
    Type: CommaDelimitedList
    Default: "Users,Orders,Products"

Resources:
  Fn::ForEach::Services:
    - Name
    - !Ref ServiceNames
    - ${Name}Function:
        Type: AWS::Serverless::Function
        Properties:
          Handler: index.handler
          Runtime: python3.12
          CodeUri: ./services/${Name}
```

Running `sam build` expands this into `UsersFunction`, `OrdersFunction`, and `ProductsFunction`, each built from its respective source directory.

### Dynamic artifact properties

When a packageable property uses a loop variable (e.g., `./services/${Name}`), SAM CLI generates a CloudFormation `Mappings` section that maps each collection value to its S3 URI. The `Fn::ForEach` body is rewritten to use `Fn::FindInMap` so CloudFormation can resolve the correct artifact at deploy time.

The set of recognized artifact properties is derived from the same canonical list `sam package` already uses (`RESOURCES_WITH_LOCAL_PATHS` and `RESOURCES_WITH_IMAGE_COMPONENT` in `samcli/lib/utils/resources.py`), so every resource type whose artifact property `sam package` would normally rewrite is supported here too. That includes:

| Resource type | Property |
|---------------|----------|
| `AWS::Serverless::Function` | `CodeUri`, `ImageUri` |
| `AWS::Serverless::LayerVersion` | `ContentUri` |
| `AWS::Serverless::Api` | `DefinitionUri` |
| `AWS::Serverless::HttpApi` | `DefinitionUri` |
| `AWS::Serverless::StateMachine` | `DefinitionUri` |
| `AWS::Serverless::GraphQLApi` | `SchemaUri`, `CodeUri` |
| `AWS::Serverless::Application` | `Location` |
| `AWS::Lambda::Function` | `Code`, `Code.ImageUri` |
| `AWS::Lambda::LayerVersion` | `Content` |
| `AWS::ApiGateway::RestApi` | `BodyS3Location` |
| `AWS::ApiGatewayV2::Api` | `BodyS3Location` |
| `AWS::AppSync::GraphQLSchema` | `DefinitionS3Location` |
| `AWS::AppSync::Resolver` | `RequestMappingTemplateS3Location`, `ResponseMappingTemplateS3Location`, `CodeS3Location` |
| `AWS::AppSync::FunctionConfiguration` | `RequestMappingTemplateS3Location`, `ResponseMappingTemplateS3Location`, `CodeS3Location` |
| `AWS::StepFunctions::StateMachine` | `DefinitionS3Location` |
| `AWS::ElasticBeanstalk::ApplicationVersion` | `SourceBundle` |
| `AWS::Glue::Job` | `Command.ScriptLocation` |
| `AWS::CloudFormation::Stack` | `TemplateURL` |
| `AWS::CloudFormation::StackSet` | `TemplateURL` |
| `AWS::CloudFormation::ModuleVersion` | `ModulePackage` |
| `AWS::CloudFormation::ResourceVersion` | `SchemaHandlerPackage` |

When a property is dotted (e.g. `Command.ScriptLocation` on `AWS::Glue::Job` or `Code.ImageUri` on `AWS::Lambda::Function`), SAM CLI reads and writes the value at the dotted location on the resource — so it lands at `Properties.Command.ScriptLocation` rather than at a literal `Properties["Command.ScriptLocation"]` key — and uses only the leaf segment when it needs to construct an alphanumeric identifier (Mapping name suffix or `Fn::FindInMap` third argument).

When the property is loop-templated, the Mapping name is `SAM<LeafProperty><LoopName>` (e.g., `SAMCodeUriServices`, `SAMScriptLocationJobs`). Customer-authored mappings should not start with these `SAM*` prefixes — they are reserved for SAM CLI (see [Limitations](#limitations) below).

For example, after `sam package`:

```yaml
Mappings:
  SAMCodeUriServices:
    Users:
      CodeUri: s3://my-bucket/abc123
    Orders:
      CodeUri: s3://my-bucket/def456
    Products:
      CodeUri: s3://my-bucket/ghi789

Resources:
  Fn::ForEach::Services:
    - Name
    - !Ref ServiceNames
    - ${Name}Function:
        Type: AWS::Serverless::Function
        Properties:
          Handler: index.handler
          Runtime: python3.12
          CodeUri: !FindInMap [SAMCodeUriServices, !Ref Name, CodeUri]
```

### Multiple resources per ForEach body

A single `Fn::ForEach` body can emit more than one resource per iteration. Each resource is generated for every collection value:

```yaml
Resources:
  Fn::ForEach::Tables:
    - TableName
    - [Users, Orders, Products]
    - ${TableName}Table:
        Type: AWS::DynamoDB::Table
        Properties:
          TableName: !Sub "${AWS::StackName}-${TableName}"
          # ...

      ${TableName}StreamProcessor:
        Type: AWS::Serverless::Function
        Properties:
          CodeUri: stream-processors/${TableName}/
          Events:
            DDBStream:
              Type: DynamoDB
              Properties:
                Stream: !GetAtt
                  - !Sub "${TableName}Table"
                  - StreamArn
```

### Mapping name collision resolution

When two resources in the same `Fn::ForEach` body declare the same dynamic artifact property (for example, both an `Api` and a `StateMachine` use `DefinitionUri`), SAM CLI appends a sanitized suffix derived from the resource logical-ID template to keep Mapping names unique:

| Resource template | Property | Mapping name |
|-------------------|----------|--------------|
| `${Svc}Api` | `DefinitionUri` | `SAMDefinitionUriServicesApi` |
| `${Svc}StateMachine` | `DefinitionUri` | `SAMDefinitionUriServicesStateMachine` |

When there is no collision the base name (e.g., `SAMDefinitionUriServices`) is used.

### Parameter-based collections

When the `Fn::ForEach` collection is a parameter reference (`!Ref ServiceNames`), the collection values are resolved at package time from:

1. `--parameter-overrides` passed to `sam build` or `sam package`
2. The parameter's `Default` value in the template

**Important:** If you change the parameter value at deploy time (e.g., adding a new service), you must re-package first so the Mappings include entries for the new values.

```bash
# Package with the values you intend to deploy with
sam package --parameter-overrides ServiceNames="Users,Orders,Products"

# Deploy with the same values
sam deploy --parameter-overrides ServiceNames="Users,Orders,Products"
```

### Nested stacks

`Fn::ForEach` in nested stack templates (`AWS::CloudFormation::Stack`) is supported. SAM CLI passes the parent stack's `Parameters` property to the child template expansion, so child `Fn::ForEach` collections that reference parent-supplied parameters resolve correctly.

```yaml
# parent.yaml
Resources:
  ChildStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: ./child.yaml
      Parameters:
        ServiceNames: "Users,Orders,Products"
```

### Nested Fn::ForEach

Up to 5 levels of nesting are supported, matching CloudFormation's limit:

```yaml
Resources:
  Fn::ForEach::Envs:
    - Env
    - [Dev, Staging, Prod]
    - Fn::ForEach::Services:
        - Svc
        - [Users, Orders]
        - ${Env}${Svc}Function:
            Type: AWS::Serverless::Function
            Properties:
              CodeUri: ./services/${Svc}
              Environment:
                Variables:
                  STAGE: !Ref Env
```

### ForEach in Outputs

`Fn::ForEach` blocks are also expanded inside the `Outputs` section, so you can emit one output per collection value:

```yaml
Outputs:
  Fn::ForEach::FunctionArns:
    - Name
    - [alpha, beta]
    - ${Name}FunctionArn:
        Value: !GetAtt
          - !Sub "${Name}Function"
          - Arn
```

### Conditions and DependsOn

Resources emitted by `Fn::ForEach` can carry `Condition` and `DependsOn` like any other resource. The condition or dependency is replicated onto each generated resource:

```yaml
Conditions:
  IsProd: !Equals [!Ref Environment, prod]

Resources:
  SharedTable:
    Type: AWS::DynamoDB::Table
    # ...

  Fn::ForEach::Functions:
    - Name
    - [api, worker]
    - ${Name}Function:
        Type: AWS::Serverless::Function
        Condition: IsProd
        DependsOn: SharedTable
        Properties:
          Handler: main.handler
          CodeUri: functions/${Name}/
```

### &{identifier} syntax

The `&{identifier}` syntax strips non-alphanumeric characters from the substituted value, useful for generating valid logical IDs from values like IP addresses:

```yaml
Fn::ForEach::Hosts:
  - IP
  - ["10.0.0.1", "10.0.0.2"]
  - Host&{IP}:
      Type: AWS::EC2::Instance
      # Expands to Host10001, Host10002
```

## Supported intrinsic functions

The following intrinsic functions are resolved locally during expansion:

| Function | Description |
|----------|-------------|
| `Fn::ForEach` | Loop expansion |
| `Fn::Length` | Returns count of list elements |
| `Fn::ToJsonString` | Converts value to JSON string |
| `Fn::FindInMap` | Map lookup (with optional `DefaultValue`) |
| `Fn::If` | Conditional value selection |
| `Fn::Sub` | String substitution |
| `Fn::Join` | String concatenation |
| `Fn::Split` | String splitting |
| `Fn::Select` | List element selection |
| `Fn::Base64` | Base64 encoding |
| `Fn::Equals` / `Fn::And` / `Fn::Or` / `Fn::Not` | Condition evaluation |
| `Ref` | Parameter and pseudo-parameter references |

Functions that require deployed resources (`Fn::GetAtt`, `Fn::ImportValue`, `Fn::GetAZs`) are preserved for CloudFormation to resolve at deploy time.

## AWS::Include processing order

When a template uses both `Fn::Transform: AWS::Include` and
`Transform: AWS::LanguageExtensions`, SAM CLI processes the inline
`AWS::Include` macros **before** running language-extension expansion
locally. This mirrors CloudFormation's server-side transform pipeline,
where `Fn::Transform` macros are resolved before
`AWS::LanguageExtensions`.

The practical effect is that `AWS::Include` `Location` rewrites work
correctly even when the include lives buried inside language-extension
functions like `Fn::ToJsonString` or `Fn::ForEach` bodies, because the
include is rewritten while still structurally visible — before
`Fn::ToJsonString` collapses subtrees into JSON-string literals or
`Fn::ForEach` expands resources.

## Validation errors

The following template issues are caught locally before the SAM transform runs:

| Cause | Error message |
|-------|---------------|
| The `Fn::ForEach` value is malformed — not a list, doesn't have exactly 3 elements, or has a non-string loop identifier. | `Fn::ForEach::<key> layout is incorrect` (raised as `InvalidTemplateException`; see `samcli/lib/cfn_language_extensions/processors/foreach.py`). |
| More than 5 levels of `Fn::ForEach` are nested. | `Fn::ForEach nesting depth of <N> exceeds the maximum allowed depth of 5. CloudFormation supports up to 5 nested Fn::ForEach loops.` |
| The collection resolves to an empty list (e.g., a `CommaDelimitedList` parameter with `Default: ""`). | No error — the loop is silently skipped and no resources are emitted. |
| The `!Ref` in the collection points at a parameter that is not declared in the template. | No error in the typical `sam build` / `sam package` flow. SAM CLI runs intrinsic resolution in PARTIAL mode and preserves the unresolved `{"Ref": "<name>"}`. At deploy time, CloudFormation will resolve it server side. |

## Limitations

- **Collections must be resolvable at build/package time.** `Fn::ForEach` collections that use `Fn::GetAtt`, `Fn::ImportValue`, or SSM/Secrets Manager dynamic references cannot be expanded locally. Use a parameter with `--parameter-overrides` instead.
- **Parameter values are fixed at package time.** If you change `--parameter-overrides` at deploy time without re-packaging, the Mappings won't include entries for new values and deployment will fail.
- **`DeletionPolicy` and `UpdateReplacePolicy`** are validated and resolved during expansion. They support `Ref` to parameters but not other intrinsic functions.
- **Nesting limit.** Up to 5 levels of `Fn::ForEach` may be nested, matching CloudFormation's server-side limit.
- **Reserved Mapping names.** Mapping names starting with any of the following are reserved for SAM CLI — do not author your own mappings with these prefixes:
  - `SAMCodeUri`, `SAMImageUri`, `SAMContentUri`, `SAMDefinitionUri`, `SAMSchemaUri`, `SAMBodyS3Location`, `SAMDefinitionS3Location`, `SAMTemplateURL`, `SAMCode`, `SAMContent` — emitted by `sam package` for dynamic artifact properties (see the table above).
  - `SAMLayers` — emitted by `sam build` when a `Fn::ForEach`-generated function picks up auto-generated dependency-layer references (Lambda layers SAM CLI builds into a nested stack). This prefix has no corresponding user-authored property; it is added automatically.

## Telemetry

SAM CLI emits a `CFNLanguageExtensions` telemetry event when a command is invoked with `--language-extensions` (or its env-var equivalent) **and** the template declares the `AWS::LanguageExtensions` transform. The event fires once per invocation; no template content is transmitted. When local processing is off (the default), no event fires.
