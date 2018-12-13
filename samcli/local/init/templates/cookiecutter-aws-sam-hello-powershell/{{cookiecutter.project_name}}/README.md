# {{ cookiecutter.project_name }}

This is a sample template for {{ cookiecutter.project_name }}


## Requirements

* AWS CLI already configured with Administrator permission
* [Docker installed](https://www.docker.com/community-edition)
* [SAM CLI installed](https://github.com/awslabs/aws-sam-cli)
* [.NET Core installed](https://www.microsoft.com/net/download)
* [PowerShell Core installed](https://docs.microsoft.com/en-us/powershell/scripting/setup/installing-powershell?view=powershell-6)
* [AWSLambdaPSCore PowerShell module](https://www.powershellgallery.com/packages/AWSLambdaPSCore/1.1.0.0)
* [Pester PowerShell module](https://github.com/pester/Pester)

## Setup process

### PowerShell (all Operating Systems)

```powershell
build.ps1
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

AWS Lambda PowerShell functions are compiled in to a .net core project before they are uploaded. Depencies are detected through the `#Requires` statement in your script file. After your project is built SAM will use `CodeUri` property to know where to look for the built application (including its dependencies):

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
    --template-file template.yaml \
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

### Powershell (all Operating Systems)

```powershell
Invoke-Pester '[path to test directory]'
```

This will run all files that end in `tests.ps1` in that directory.

# Appendix

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
    --template-file template.yaml \
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
