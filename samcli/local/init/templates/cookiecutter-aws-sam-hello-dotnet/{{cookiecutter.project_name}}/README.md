# {{ cookiecutter.project_name }}

This is a sample template for {{ cookiecutter.project_name }}


## Requirements

* AWS CLI already configured with Administrator permission
* [Docker installed](https://www.docker.com/community-edition)
* [SAM CLI installed](https://github.com/awslabs/aws-sam-cli)
* [.NET Core installed](https://www.microsoft.com/net/download)

Please see the [currently supported patch of each major version of .NET Core](https://github.com/aws/aws-lambda-dotnet#version-status) to ensure your functions are compatible with the AWS Lambda runtime.

## Recommended Tools for Visual Studio / Visual Studio Code Users

* [AWS Toolkit for Visual Studio](https://aws.amazon.com/visualstudio/)
* [AWS Extensions for .NET CLI](https://github.com/aws/aws-extensions-for-dotnet-cli) which are AWS extensions to the .NET CLI focused on building .NET Core and ASP.NET Core applications and deploying them to AWS services including Amazon Elastic Container Service, AWS Elastic Beanstalk and AWS Lambda.

> **Note: this project uses [Cake Build](https://cakebuild.net/) for build, test and packaging requirements. You do not need to have the [AWS Extensions for .NET CLI](https://github.com/aws/aws-extensions-for-dotnet-cli) installed, but are free to do so if you which to use them. Version 3 of the Amazon.Lambda.Tools does require .NET Core 2.1 for installation, but can be used to deploy older versions of .NET Core.**

## Setup process

### Linux & macOS

```bash
sh build.sh --target=Package
```

### Windows (Powershell)

```powershell
build.ps1 --target=Package
```

### Local development

**Invoking function locally using a local sample payload**

```bash
sam local invoke HelloWorldFunction --event event.json
```

**Invoking function locally through local API Gateway**

```bash
sam local start-api
```

**SAM Local** is used to emulate both Lambda and API Gateway locally and uses our `template.yaml` to understand how to bootstrap this environment (runtime, where the source code is, etc.) - The following excerpt is what the CLI will read in order to initialize an API and its routes:

```yaml
...
Events:
    HelloWorldFunction:
        Type: Api # More info about API Event Source: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#api
        Properties:
            Path: /hello
            Method: get
```

If the previous command run successfully you should now be able to hit the following local endpoint to invoke your function `http://localhost:3000/hello`

## Packaging and deployment

AWS Lambda C# runtime requires a flat folder with all dependencies including the application. SAM will use `CodeUri` property to know where to look up for both application and dependencies:

```yaml
...
    HelloWorldFunction:
        Type: AWS::Serverless::Function
        Properties:
            CodeUri: artifacts/HelloWorld.zip            
            ...
```

First and foremost, we need an `S3 bucket` where we can upload our Lambda functions packaged as ZIP before we deploy anything - If you don't have a S3 bucket to store code artifacts then this is a good time to create one:

```bash
aws s3 mb s3://BUCKET_NAME
```

Next, run the following command to package our Lambda function to S3:

```bash
sam package \
    --output-template-file packaged.yaml \
    --s3-bucket REPLACE_THIS_WITH_YOUR_S3_BUCKET_NAME
```

Next, the following command will create a Cloudformation Stack and deploy your SAM resources.

```bash
sam deploy \
    --template-file packaged.yaml \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} \
    --capabilities CAPABILITY_IAM
```

> **See [Serverless Application Model (SAM) HOWTO Guide](https://github.com/awslabs/serverless-application-model/blob/master/HOWTO.md) for more details in how to get started.**

After deployment is complete you can run the following command to retrieve the API Gateway Endpoint URL:

```bash
aws cloudformation describe-stacks \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} \
    --query 'Stacks[].Outputs[?OutputKey==`HelloWorldApi`]' \
    --output table
```

## Testing

### Linux & macOS

```bash
sh build.sh --target=Test
```

### Windows (Powershell)

```powershell
build.ps1 --target=Test
```

# Appendix

## Bringing to the next level

Here are a few things you can try to get more acquainted with building serverless applications using SAM:

### Create an additional API resource

* Create a catch all resource (e.g. /hello/{proxy+}) and return the name requested through this new path
* Update tests

### Step-through debugging

* **[Enable step-through debugging docs for supported runtimes]((https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-debugging.html))**

Next, you can use AWS Serverless Application Repository to deploy ready to use Apps that go beyond hello world samples and learn how authors developed their applications: [AWS Serverless Application Repository main page](https://aws.amazon.com/serverless/serverlessrepo/)

## SAM and AWS CLI commands

All commands used throughout this document

```bash
# Invoke function locally with event.json as an input
sam local invoke HelloWorldFunction --event event.json

# Run API Gateway locally
sam local start-api

# Create S3 bucket
aws s3 mb s3://BUCKET_NAME

# Package Lambda function defined locally and upload to S3 as an artifact
sam package \
    --output-template-file packaged.yaml \
    --s3-bucket REPLACE_THIS_WITH_YOUR_S3_BUCKET_NAME

# Deploy SAM template as a CloudFormation stack
sam deploy \
    --template-file packaged.yaml \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} \
    --capabilities CAPABILITY_IAM

# Describe Output section of CloudFormation stack previously created
aws cloudformation describe-stacks \
    --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} \
    --query 'Stacks[].Outputs[?OutputKey==`HelloWorldApi`]' \
    --output table

# Tail Lambda function Logs using Logical name defined in SAM Template
sam logs -n HelloWorldFunction --stack-name {{ cookiecutter.project_name.lower().replace(' ', '-') }} --tail
```
