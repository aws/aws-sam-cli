AWS SAM CLI: Root command help test Design
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

The help text could be changed to look like below. Only the options are showcased here and not the 

```

Options:

  *Required Options:*

  -t, --template-file, --template PATH
                                  AWS SAM template file.  [default: template.[yaml|yml|json]]
  --stack-name TEXT               The name of the AWS CloudFormation stack deploying to. If you specify an
                                  existing stack, the command updates the stack. If you specify a new stack, the
                                  command creates it.  [required]

  *Debug Options:*

  --debug                         Turn on debug logging to print debug message generated by SAM CLI and display
                                  timestamps.

  Configuration Options:
  
  --config-env TEXT               The environment name specifying the default parameter values in the configuration
                                  file to use. Its default value is 'default'. For more information about
                                  configuration files, see: https://docs.aws.amazon.com/serverless-application-
                                  model/latest/developerguide/serverless-sam-cli-config.html.

  --config-file TEXT              The path and file name of the configuration file containing default parameter values
                                  to use. Its default value is 'samconfig.toml' in project directory. For more
                                  information about configuration files, see: https://docs.aws.amazon.com/serverless-
                                  application-model/latest/developerguide/serverless-sam-cli-config.html.


  *AWS Credential Options:*
  
  --profile TEXT                  Select a specific profile from your credential file to get AWS credentials.
  --region TEXT                   Set the AWS Region of the service (e.g. us-east-1).


  *Advanced Options:*
  
  --code                          Sync code resources. This includes Lambda Functions, API Gateway, and Step
                                  Functions.

  --watch                         Watch local files and automatically sync with remote.
  --resource-id TEXT              Sync code for all the resources with the ID. To sync a resource within a nested
                                  stack, use the following pattern {ChildStack}/{logicalId}.

  --resource RESOURCE
                                  Sync code for all resources of the given resource type. Accepted values are
                                  ['AWS::Serverless::Function', 'AWS::Lambda::Function',
                                  'AWS::Serverless::LayerVersion', 'AWS::Lambda::LayerVersion',
                                  'AWS::Serverless::Api', 'AWS::ApiGateway::RestApi', 'AWS::Serverless::HttpApi',
                                  'AWS::ApiGatewayV2::Api', 'AWS::Serverless::StateMachine',
                                  'AWS::StepFunctions::StateMachine']

  --dependency-layer / --no-dependency-layer
                                  This option separates the dependencies of individual function into another layer,
                                  for speeding up the sync.process



  -s, --base-dir DIRECTORY        Resolve relative paths to function's source code with respect to this folder. Use
                                  this if SAM template and your source code are not in same enclosing folder. By
                                  default, relative paths are resolved with respect to the SAM template's location

  -u, --use-container             If your functions depend on packages that have natively compiled dependencies, use
                                  this flag to build your function inside an AWS Lambda-like Docker container

  Infra Options:

  --image-repository              ECR repo uri where this command uploads the image artifacts that are referenced in
                                  your template.

  --image-repositories            Specify mapping of Function Logical ID to ECR Repo uri, of the form
                                  Function_Logical_ID=ECR_Repo_Uri.This option can be specified multiple times.

  --s3-bucket TEXT                The name of the S3 bucket where this command uploads the artifacts that are
                                  referenced in your template.

  --s3-prefix TEXT                A prefix name that the command adds to the artifacts name when it uploads them to
                                  the S3 bucket. The prefix name is a path name (folder name) for the S3 bucket.

  --kms-key-id TEXT               The ID of an AWS KMS key that the command uses to encrypt artifacts that are at rest
                                  in the S3 bucket.

  --role-arn TEXT                 The Amazon Resource Name (ARN) of an AWS Identity and Access Management (IAM) role
                                  that AWS CloudFormation assumes when executing the change set.

  --parameter-overrides           Optional. A string that contains AWS CloudFormation parameter overrides encoded as
                                  key=value pairs.For example, 'ParameterKey=KeyPairName,ParameterValue=MyKey
                                  ParameterKey=InstanceType,ParameterValue=t1.micro' or KeyPairName=MyKey
                                  InstanceType=t1.micro


  --metadata                      Optional. A map of metadata to attach to ALL the artifacts that are referenced in
                                  your template.

  --notification-arns LIST        Amazon  Simple  Notification  Service  topicAmazon  Resource  Names  (ARNs) that AWS
                                  CloudFormation associates withthe stack.

  --tags                          A list of tags to associate with the stack that is created or updated.AWS
                                  CloudFormation also propagates these tags to resources in the stack if the resource
                                  supports it.

  --capabilities LIST             A list of capabilities that you must specify before AWS Cloudformation can create
                                  certain stacks. Some stack templates might include resources that can affect
                                  permissions in your AWS account, for example, by creating new AWS Identity and
                                  Access Management (IAM) users. For those stacks, you must explicitly acknowledge
                                  their capabilities by specifying this parameter. The only valid valuesare
                                  CAPABILITY_IAM and CAPABILITY_NAMED_IAM. If you have IAM resources, you can specify
                                  either capability. If you have IAM resources with custom names, you must specify
                                  CAPABILITY_NAMED_IAM. If you don't specify this parameter, this action returns an
                                  InsufficientCapabilities error.
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
