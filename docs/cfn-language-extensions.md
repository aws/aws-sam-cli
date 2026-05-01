# CloudFormation Language Extensions Support

SAM CLI now supports templates that use the `AWS::LanguageExtensions` transform, including `Fn::ForEach`, `Fn::Length`, `Fn::ToJsonString`, and `Fn::FindInMap` with `DefaultValue`.

## How it works

When SAM CLI detects `AWS::LanguageExtensions` in a template's `Transform` section, it expands language extension constructs locally before running SAM transforms. This enables `sam build`, `sam package`, `sam deploy`, `sam sync`, `sam validate`, `sam local invoke`, and `sam local start-api` to work with templates that use these constructs.

The expansion happens in two phases:

1. **Phase 1 (Language Extensions)** — `Fn::ForEach` loops are expanded, intrinsic functions are resolved where possible, and the template is converted to standard CloudFormation.
2. **Phase 2 (SAM Transform)** — The expanded template is processed by the SAM Translator as usual.

The original template (with `Fn::ForEach` intact) is preserved for CloudFormation deployment, since CloudFormation processes the `AWS::LanguageExtensions` transform server-side.

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

When a packageable property (like `CodeUri`, `ContentUri`, `ImageUri`) uses a loop variable (e.g., `./services/${Name}`), SAM CLI generates a CloudFormation `Mappings` section that maps each collection value to its S3 URI. The `Fn::ForEach` body is rewritten to use `Fn::FindInMap` so CloudFormation can resolve the correct artifact at deploy time.

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

## Limitations

- **Collections must be resolvable at build/package time.** `Fn::ForEach` collections that use `Fn::GetAtt`, `Fn::ImportValue`, or SSM/Secrets Manager dynamic references cannot be expanded locally. Use a parameter with `--parameter-overrides` instead.
- **Parameter values are fixed at package time.** If you change `--parameter-overrides` at deploy time without re-packaging, the Mappings won't include entries for new values and deployment will fail.
- **`DeletionPolicy` and `UpdateReplacePolicy`** are validated and resolved during expansion. They support `Ref` to parameters but not other intrinsic functions.

## Telemetry

SAM CLI tracks usage of `AWS::LanguageExtensions` via the `CFNLanguageExtensions` telemetry feature flag. No template content is transmitted.
