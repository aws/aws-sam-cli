# AWS SAM Hello World Example #

A simple AWS SAM template that specifies a single Lambda function.

## Usage ##

To create and deploy the SAM Hello World example, first ensure that you've met the requirements described in the [root README](../../README.md). Then follow the steps below.

### Test your application locally ###

Use [SAM Local](https://github.com/awslabs/aws-sam-local) to run your Lambda function locally:

    sam local invoke "HelloWorld" -e event.json

### Package artifacts ###

Run the following command, replacing `BUCKET-NAME` with the name of your bucket:

    sam package --template-file template.yaml --s3-bucket BUCKET-NAME --output-template-file packaged-template.yaml

This creates a new template file, packaged-template.yaml, that you will use to deploy your serverless application.

### Deploy to AWS CloudFormation ###

Run the following command, replacing `MY-NEW-STACK` with a name for your CloudFormation stack.

    sam deploy --template-file packaged-template.yaml --stack-name MY-NEW-STACK --capabilities CAPABILITY_IAM

This uploads your template to an S3 bucket and deploys the specified resources using AWS CloudFormation.
