AWS SAM CLI: Per command help test Design
==========================================

What is the problem?
--------------------

Currently AWS SAM CLI's command help text per command does not have a common structure, they all follow different formats without consistency.


Current state of the world as of v1.75.0 for one of the commands. It is a giant wall of text.


```
Usage: sam sync [OPTIONS]

  Update/Sync local artifacts to AWS

  By default, the sync command runs a full stack update. You can specify
  --code or --watch to switch modes.  Sync also supports nested stacks and
  nested stack resources. For example

  $ sam sync --code --stack-name {stack} --resource-id \
  {ChildStack}/{ResourceId}

  Running --watch with --code option will provide a way to run code
  synchronization only, that will speed up start time and will skip any
  template change. Please remember to update your deployed stack by running
  without --code option.

  $ sam sync --code --watch --stack-name {stack}

Options:
  --config-env TEXT               The environment name specifying the default
                                  parameter values in the configuration file
                                  to use. Its default value is 'default'. For
                                  more information about configuration files,
                                  see: https://docs.aws.amazon.com/serverless-
                                  application-
                                  model/latest/developerguide/serverless-sam-
                                  cli-config.html.
  --config-file TEXT              The path and file name of the configuration
                                  file containing default parameter values to
                                  use. Its default value is 'samconfig.toml'
                                  in project directory. For more information
                                  about configuration files, see:
                                  https://docs.aws.amazon.com/serverless-
                                  application-
                                  model/latest/developerguide/serverless-sam-
                                  cli-config.html.
  -t, --template-file, --template PATH
                                  AWS SAM template file.  [default:
                                  template.[yaml|yml|json]]
  --code                          Sync code resources. This includes Lambda
                                  Functions, API Gateway, and Step Functions.
  --watch                         Watch local files and automatically sync
                                  with remote.
  --resource-id TEXT              Sync code for all the resources with the ID.
                                  To sync a resource within a nested stack,
                                  use the following pattern
                                  {ChildStack}/{logicalId}.
  --resource [AWS::Serverless::Function|AWS::Lambda::Function|AWS::Serverless::LayerVersion|AWS::Lambda::LayerVersion|AWS::Serverless::Api|AWS::ApiGateway::RestApi|AWS::Serverless::HttpApi|AWS::ApiGatewayV2::Api|AWS::Serverless::StateMachine|AWS::StepFunctions::StateMachine]
                                  Sync code for all resources of the given
                                  resource type. Accepted values are
                                  ['AWS::Serverless::Function',
                                  'AWS::Lambda::Function',
                                  'AWS::Serverless::LayerVersion',
                                  'AWS::Lambda::LayerVersion',
                                  'AWS::Serverless::Api',
                                  'AWS::ApiGateway::RestApi',
                                  'AWS::Serverless::HttpApi',
                                  'AWS::ApiGatewayV2::Api',
                                  'AWS::Serverless::StateMachine',
                                  'AWS::StepFunctions::StateMachine']
  --dependency-layer / --no-dependency-layer
                                  This option separates the dependencies of
                                  individual function into another layer, for
                                  speeding up the sync.process
  --stack-name TEXT               The name of the AWS CloudFormation stack
                                  you're deploying to. If you specify an
                                  existing stack, the command updates the
                                  stack. If you specify a new stack, the
                                  command creates it.  [required]
  -s, --base-dir DIRECTORY        Resolve relative paths to function's source
                                  code with respect to this folder. Use this
                                  if SAM template and your source code are not
                                  in same enclosing folder. By default,
                                  relative paths are resolved with respect to
                                  the SAM template's location
  -u, --use-container             If your functions depend on packages that
                                  have natively compiled dependencies, use
                                  this flag to build your function inside an
                                  AWS Lambda-like Docker container
  --image-repository              ECR repo uri where this command uploads the
                                  image artifacts that are referenced in your
                                  template.
  --image-repositories            Specify mapping of Function Logical ID to
                                  ECR Repo uri, of the form
                                  Function_Logical_ID=ECR_Repo_Uri.This option
                                  can be specified multiple times.
  --s3-bucket TEXT                The name of the S3 bucket where this command
                                  uploads the artifacts that are referenced in
                                  your template.
  --s3-prefix TEXT                A prefix name that the command adds to the
                                  artifacts name when it uploads them to the
                                  S3 bucket. The prefix name is a path name
                                  (folder name) for the S3 bucket.
  --kms-key-id TEXT               The ID of an AWS KMS key that the command
                                  uses to encrypt artifacts that are at rest
                                  in the S3 bucket.
  --role-arn TEXT                 The Amazon Resource Name (ARN) of an AWS
                                  Identity and Access Management (IAM) role
                                  that AWS CloudFormation assumes when
                                  executing the change set.
  --parameter-overrides           Optional. A string that contains AWS
                                  CloudFormation parameter overrides encoded
                                  as key=value pairs.For example, 'ParameterKe
                                  y=KeyPairName,ParameterValue=MyKey Parameter
                                  Key=InstanceType,ParameterValue=t1.micro' or
                                  KeyPairName=MyKey InstanceType=t1.micro
  --debug                         Turn on debug logging to print debug message
                                  generated by AWS SAM CLI and display
                                  timestamps.
  --profile TEXT                  Select a specific profile from your
                                  credential file to get AWS credentials.
  --region TEXT                   Set the AWS Region of the service (e.g. us-
                                  east-1).
  --metadata                      Optional. A map of metadata to attach to ALL
                                  the artifacts that are referenced in your
                                  template.
  --notification-arns LIST        Amazon  Simple  Notification  Service
                                  topicAmazon  Resource  Names  (ARNs) that
                                  AWS CloudFormation associates withthe stack.
  --tags                          A list of tags to associate with the stack
                                  that is created or updated.AWS
                                  CloudFormation also propagates these tags to
                                  resources in the stack if the resource
                                  supports it.
  --capabilities LIST             A list of capabilities that you must specify
                                  before AWS Cloudformation can create certain
                                  stacks. Some stack templates might include
                                  resources that can affect permissions in
                                  your AWS account, for example, by creating
                                  new AWS Identity and Access Management (IAM)
                                  users. For those stacks, you must explicitly
                                  acknowledge their capabilities by specifying
                                  this parameter. The only valid valuesare
                                  CAPABILITY_IAM and CAPABILITY_NAMED_IAM. If
                                  you have IAM resources, you can specify
                                  either capability. If you have IAM resources
                                  with custom names, you must specify
                                  CAPABILITY_NAMED_IAM. If you don't specify
                                  this parameter, this action returns an
                                  InsufficientCapabilities error.
  -h, --help                      Show this message and exit.

```

Users would probably have a ton of questions based on that help text. Some things that come up top of mind are below.

* Which options are required?
* What are the options that are AWS infra related? AWS Credentials related?
* Which ones are about additional information for developers?
* How can options be ordered such that is about incremental exposure to complexity?

What will be changed?
---------------------

All help text will be following a certain structure like below.

```commandline
Usage: **sam sub-command** [OPTIONS]

1-liner explanation of what the sub-command does. 
It should directly map to the lifecycle shown in root help text.

Examples:

```$sam sub-command --options```

  **This command does not require/requires access to AWS credentials.**
  
More detailed explanation.

Workflows:
    $ sam command -> **sam sub-command**

Acronyms:
    IAM : Identity and Access Management.
    ARN: Amazon Resource Name.
    SNS: Simple Notification Service.
    ECR: Elastic Container Registy
    KMS: Key Management Service.

Options:

    **Required Options:**
        ...
    AWS Credential Options: (Ordering changes on a per command basis)
        ....
    Configuration Options:
        ....
    Infrastructure Options:
        ....
    Additional Options:
        ....
    Verbosity Options:
        ....
    
```

The sync help text could be changed to look like below. Only the options are showcased here.

```bash
Usage: sam sync [OPTIONS]

  NEW! Sync an AWS SAM Project to AWS.

  Examples:
  $ sam sync --code --stack-name {stack} --resource-id \
  {ChildStack}/{ResourceId}
  
  $ sam sync --code --watch --stack-name {stack}
  
  By default, the sync command runs a full AWS Cloudformation stack update. You can specify
  --code or --watch to switch modes. Sync also supports nested stacks and
  nested stack resources.

  Running --watch with --code option will provide a way to run code
  synchronization only, that will speed up start time and will skip any
  template change. Please remember to update your deployed stack by running
  without --code option.
  
  **This command requires access to AWS credentials.**

Acronyms:

    IAM: Identity and Access Management.
    ARN: Amazon Resource Name.
    SNS: Simple Notification Service.
    ECR: Elastic Container Registy
    KMS: Key Management Service.

Options:

  Required Options:

  -t, --template-file, --template PATH    AWS SAM template file.  [default: template.[yaml|yml|json]]
  --stack-name TEXT                       Name of the AWS CloudFormation stack. 

  AWS Credential Options:
  
  Exploratory DESIGN NOTE: How can we streamline credentials
  
  --profile TEXT                  Named profile for AWS credentials.
  --region TEXT                   Set the AWS Region. (e.g. us-east-1). 


  Infrastructure Options:

  --parameter-overrides           String that contains AWS CloudFormation parameter overrides encoded as
                                  key=value pairs.
                                  
                                  For example, 'ParameterKey=KeyPairName,ParameterValue=MyKey
                                  ParameterKey=InstanceType,ParameterValue=t1.micro' or KeyPairName=MyKey
                                  InstanceType=t1.micro

  --capabilities LIST             List of capabilities that one must specify before AWS Cloudformation can create
                                  certain stacks. Valid values: ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]
                                  More info at: https://docs.aws.amazon.com/serverlessrepo/latest/devguide/acknowledging-application-capabilities.html
                                  
  --s3-bucket TEXT                AWS S3 bucket where artifacts referenced in your template are uploaded.

  --s3-prefix TEXT                Prefix name that is added to the artifact's name when it is uploaded to
                                  the AWS S3 bucket.
                                  
  --image-repository              AWS ECR repository URI where referenced image artifacts are uploaded. 

  --image-repositories            Mapping of Function Logical ID to AWS ECR Repository URI
                                  Example: Function_Logical_ID=ECR_Repo_Uri.
                                  This option can be specified multiple times.

  --kms-key-id TEXT               ID of an AWS KMS key that is used to encrypt artifacts that are at rest
                                  in the AWS S3 bucket.

  --role-arn TEXT                 ARN of an IAM role that AWS CloudFormation assumes when executing the change set.


  --notification-arns LIST        ARNs of SNS topics that AWS CloudFormation associates with the stack.

  --tags                          List of tags to associate with the stack. 
                                  
  --metadata                      Map of metadata to attach to ALL the artifacts that are referenced in
                                  the template.

  Configuration Options:
  
  Learn more about configuration files at:  https://docs.aws.amazon.com/serverless-application-
                                  model/latest/developerguide/serverless-sam-cli-config.html.
  
  --config-file TEXT              Configuration file containing default parameter values. [default:'samconfig.toml']
                                  
  --config-env TEXT               Environment name specifying default parameter values in the configuration
                                  file. [default: "default"]


  Additional Options:
  
  --dependency-layer / --no-dependency-layer
                                  Separate dependencies of an individual function into a Lambda layer
                                  for improving performance.
                                  
  --watch                         Watch local files and automatically sync with cloud.
  --code                          Sync **ONLY** code resources. This includes AWS Lambda Functions, API Gateway, and Step
                                  Functions.

  --resource-id TEXT              Sync code for all the resources with the Logical ID. To sync a resource within a nested
                                  stack, use the following pattern {ChildStack}/{logicalId}.

  --resource RESOURCE             Sync code for all resources of the given resource type. Accepted values are
                                  ['AWS::Serverless::Function', 'AWS::Lambda::Function',
                                  'AWS::Serverless::LayerVersion', 'AWS::Lambda::LayerVersion',
                                  'AWS::Serverless::Api', 'AWS::ApiGateway::RestApi', 'AWS::Serverless::HttpApi',
                                  'AWS::ApiGatewayV2::Api', 'AWS::Serverless::StateMachine',
                                  'AWS::StepFunctions::StateMachine']

  -u, --use-container             Build functions within AWS Lambda-like Docker container.
  
  -s, --base-dir DIRECTORY        Resolve relative paths to AWS SAM application from base directory.


  Verbosity Options:

  --debug                         Debug logging to print debug message generated by AWS SAM CLI and display
                                  timestamps.
                                  
```

Here's a look at revamped sam build help text.

```commandline
Usage: sam build [OPTIONS] [RESOURCE_LOGICAL_ID]

  Build your AWS serverless function code.

  To use this command, update the AWS SAM template to specify the path
  to function's source code in the resource's Code or CodeUri property.

  To build on one's workstation, run this command in folder containing
  AWS SAM template. Built artifacts will be written to .aws-sam/build folder

  Examples:
  
  $ sam build

  To build within an AWS Lambda like Docker container.
  $ sam build --use-container

  To build with inline environment variables within build containers.
  $ sam build --use-container --container-env-var Function.ENV_VAR=value --container-env-var GLOBAL_ENV_VAR=value

  To build with environment variables within build containers.
  $ sam build --use-container --container-env-var-file env.json

  To build & run functions locally.
  $ sam build && sam local invoke

  To build and package for deployment.
  $ sam build && sam package --s3-bucket <bucketname>

  To build only an individual resource (function or layer) located in the SAM
  template. Downstream SAM package and deploy will deploy only this resource
  
  $ sam build MyFunction
  
  Supported Runtimes:
  1. Python 3.7, 3.8, 3.9 using PIP

  2. Nodejs 18.x, 16.x, 14.x, 12.x using NPM

  3. Ruby3.2 using Bundler

  4. Java 8, Java 11 using Gradle and Maven

  5. Dotnetcore3.1, Dotnet6 using Dotnet CLI (without --use-container flag)

  6. Go 1.x using Go Modules (without --use-container flag)


Options:
   Required Options:
    
   -t, --template-file, --template AWS SAM template file.  [default: template.[yaml|yml|json]]
    
  Configuration Options:
  
  Learn more about configuration files at:
  https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-config.html.
  
  --config-file TEXT              Configuration file containing default parameter values. [default:'samconfig.toml']
                                  
  --config-env TEXT               Environment name specifying default parameter values in the configuration
                                  file. [default: "default"]
  AWS Credential Options:
  
  Exploratory DESIGN NOTE: How can we streamline credentials
  
  --profile TEXT                  Named profile for AWS credentials.
  --region TEXT                   Set the AWS Region. (e.g. us-east-1). 
  
  Container Options:
  
  -u, --use-container             For functions that depend on packages which
                                  have natively compiled dependencies, use
                                  this flag to build functions inside an
                                  AWS Lambda-like Docker container
                                  
  -e, --container-env-var TEXT    Input environment variables through command
                                  line to pass into build containers
                                  Example: sam build --use-
                                  container --container-env-var
                                  Func1.VAR1=value1 --container-env-var
                                  VAR2=value2
                                  
  -ef, --container-env-var-file   Environment variable json file
                                  (env_vars.json) to pass into build
                                  containers.
                                  
  -bi, --build-image TEXT         Container image URIs for building
                                  functions/layers. One can specify for all
                                  functions/layers with just the image URI
                                  (--build-image public.ecr.aws/sam/build-
                                  nodejs18.x:latest). One can also specify for each
                                  individual function with (--build-image
                                  FunctionLogicalID=public.ecr.aws/sam/build-
                                  nodejs18.x:latest). A combination of the two
                                  can be used. If a function does not have
                                  build image specified or an image URI for
                                  all functions, the default AWS SAM CLI build
                                  images will be used.
                                  
  --skip-pull-image               Skip pulling down the latest Docker image
                                  for Lambda runtime.
                                  
  --docker-network TEXT           Name or ID of an existing
                                  docker network for AWS Lambda docker containers
                                  to connect to, along with the default
                                  bridge network.
                                  If not specified, the Lambda
                                  containers will only connect to the default
                                  bridge docker network.
                                  
  Extension Options:
             
  --hook-name TEXT                ID of the hook package to be used to
                                  extend the AWS SAM CLI commands functionality.
                                  
                                  Available Hook Names ['terraform']
                                  
  --skip-prepare-infra            Skip infrastructure preparation
                                  if there have not been any
                                  infrastructure changes. 
                                  `--hook-name` is required to use this option.
                                  
  Build Stratergy Options:
                                    
  -x, --exclude TEXT              Name of the resource(s) to exclude from the
                                  SAM CLI build.
  -p, --parallel                  Enable parallel builds. 
  -m, --manifest PATH             Path to a custom dependency manifest (e.g.,
                                  package.json).
  -c, --cached / --no-cached      Enable cached builds. 

                                  Note: AWS SAM does not evaluate whether
                                  changes have been made to third party
                                  modules that your project depends on, where
                                  you have not provided a specific version.
                                  For example, if your Python function
                                  includes a requirements.txt file with the
                                  following entry requests=1.x and the latest
                                  request module version changes from 1.1 to
                                  1.2, SAM will not pull the latest version
                                  until you run a non-cached build.
   
  Artifact Location Options: 
  
  -b, --build-dir DIRECTORY       Directory where the built artifacts
                                  will be stored. This directory will be first
                                  removed before starting a build.
                                  
  -cd, --cache-dir DIRECTORY      Directory where the cache artifacts will be
                                  stored. The
                                  default cache directory is .aws-sam/cache
                                  
  -s, --base-dir DIRECTORY        Resolve relative paths to AWS SAM application from base directory.
                                  
  Template Options:
  --parameter-overrides           String that contains AWS
                                  CloudFormation parameter overrides encoded
                                  as key=value pairs.For example, 'ParameterKe
                                  y=KeyPairName,ParameterValue=MyKey Parameter
                                  Key=InstanceType,ParameterValue=t1.micro' or
                                  KeyPairName=MyKey InstanceType=t1.micro
   Beta Options:                   
  --beta-features / --no-beta-features
                                  Enable beta features.
   Verbosity Options:
                                     
  --debug                         Turn on debug logging to print debug message
                                  generated by AWS SAM CLI and display
                                  timestamps.
  -h, --help                      Show this message and exit.
```

Success criteria for the change
-------------------------------

* The success criteria for the change is less time spent on the help text to understand which options are useful.
* Increased confidence that the tool will help the user move in the right direction for their application.

Out-of-Scope
------------
* 


User Experience Walkthrough
---------------------------

Implementation
==============

CLI Changes
-----------

CLI interface will remain the same.

### Breaking Change

N/A

Design
------

There will be a separate implementation PR to showcase the changes, but it will use `click` to override commands options and help text.

`samconfig.toml` Changes
----------------

N/A

Security
--------

**What new dependencies (libraries/cli) does this change require?**

* No new dependencies

**What other Docker container images are you using?**

N/A

**Are you creating a new HTTP endpoint? If so explain how it will be
created & used**

N/A

**Are you connecting to a remote API? If so explain how is this
connection secured**

N/A

**Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?**

N/A

**How do you validate new samconfig.toml configuration?**

N/A

What is your Testing Plan (QA)?
===============================

Goal
----

Pre-requesites
--------------

Test Scenarios/Cases
--------------------

Expected Results
----------------

Pass/Fail
---------

Documentation Changes
=====================

Open Issues
============

Task Breakdown
==============

-   \[x\] Send a Pull Request with this design document
-   \[ \] Build the command line interface
-   \[ \] Build the underlying library
-   \[ \] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Run all tests on Windows
-   \[ \] Update documentation
