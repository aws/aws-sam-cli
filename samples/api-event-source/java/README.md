# AWS SAM API Event Source Example #

An example RESTful service. The Lambda function will be triggered by any HTTP request (GET, PUT, etc.)
for the root (`/`) resource.

## Usage ##

To test and deploy the example, first ensure that you've met the requirements described in the [root README](../../README.md). Then follow the steps below.

### Build your package ###

    mvn package shade:shade

### Test your application locally ###

Use [SAM Local](https://github.com/awslabs/aws-sam-local) to run your SAM application locally:

    sam local start-api

### Package artifacts ###

Run the following command, replacing `BUCKET-NAME` with the name of your bucket:

    sam package --template-file template.yaml --s3-bucket BUCKET-NAME --output-template-file packaged-template.yaml

This creates a new template file, packaged-template.yaml, that you will use to deploy your serverless application.

### Deploy to AWS ###

Run the following command, replacing `MY-NEW-STACK` with a name for your CloudFormation stack.

    sam deploy --template-file packaged-template.yaml --stack-name MY-NEW-STACK --capabilities CAPABILITY_IAM

This uploads your template to an S3 bucket and deploys the specified resources using AWS CloudFormation.
