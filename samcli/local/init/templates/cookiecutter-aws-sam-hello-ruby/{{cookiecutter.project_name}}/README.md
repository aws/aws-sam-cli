# {{ cookiecutter.project_name }}

This is a sample template for {{ cookiecutter.project_name }} - Below is a brief explanation of what we have generated for you:

```bash
.
├── README.md                   <-- This instructions file
├── event.json                  <-- API Gateway Proxy Integration event payload
├── hello_world                 <-- Source code for a lambda function
│   ├── app.rb                  <-- Lambda function code
│   ├── Gemfile                 <-- Ruby test/documentation dependencies
│   └── tests                   <-- Unit tests
│       └── unit
│           └── test_handler.rb
├── template.yaml               <-- SAM template
```

## Requirements

* AWS CLI already configured with at least PowerUser permission
* [Ruby](https://www.ruby-lang.org/en/documentation/installation/) 2.5 installed
* [Docker installed](https://www.docker.com/community-edition)

## Setup process

### Local development

**Invoking function locally using a local sample payload**

```bash
sam local invoke HelloWorldFunction --event event.json
```

**Invoking function locally through local API Gateway**

```bash
sam local start-api
```

If the previous command ran successfully you should now be able to hit the following local endpoint to invoke your function `http://localhost:3000/hello`

**SAM CLI** is used to emulate both Lambda and API Gateway locally and uses our `template.yaml` to understand how to bootstrap this environment (runtime, where the source code is, etc.) - The following excerpt is what the CLI will read in order to initialize an API and its routes:

```yaml
...
Events:
    HelloWorld:
        Type: Api # More info about API Event Source: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md#api
        Properties:
            Path: /hello
            Method: get
```

## Packaging and deployment

AWS Lambda Ruby runtime requires a flat folder with all dependencies including the application. SAM will use `CodeUri` property to know where to look up for both application and dependencies:

```yaml
...
    HelloWorldFunction:
        Type: AWS::Serverless::Function
        Properties:
            CodeUri: hello_world/
            ...
```

Firstly, we need a `S3 bucket` where we can upload our Lambda functions packaged as ZIP before we deploy anything - If you don't have a S3 bucket to store code artifacts then this is a good time to create one:

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

Run our initial unit tests:

```bash
ruby tests/unit/test_handler.rb
```

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

## Bringing to the next level

Here are a few ideas that you can use to get more acquainted as to how this overall process works:

**Idea 1**

* Create an additional API resource (e.g. /hello/{proxy+}) and return the name requested through this new path
* Update unit test to capture that
* Package & Deploy

**Idea 2**

* Create a Docker network named `sam`
* Run [DynamoDB Local via Docker](https://hub.docker.com/r/amazon/dynamodb-local/) within the `sam` network
* Change your code to connect to DynamoDB Local when running your functions locally
    - Hint: Use `endpoint` property from AWS SDK and `AWS_SAM_LOCAL` env variable to achieve that

**Idea 3**

* Enable [step-through debugging](https://github.com/awslabs/aws-sam-cli/blob/develop/docs/usage.rst#debugging-applications)

Next, you can use the following resources to know more about beyond hello world samples and how others structure their Serverless applications:

* [AWS Serverless Application Repository](https://aws.amazon.com/serverless/serverlessrepo/)
