"""
Data structure to host the root command name and short help text to speed up load time.
"""

SAM_CLI_COMMANDS = {
    "init": "Initialize an AWS SAM application.",
    "validate": "Validate an AWS SAM template.",
    "build": "Build your AWS serverless function code.",
    "local": "Run your AWS serverless function locally.",
    "remote": "Invoke or send an event to cloud resources in your AWS Cloudformation stack.",
    "package": "Package an AWS SAM application.",
    "deploy": "Deploy an AWS SAM application.",
    "delete": "Delete an AWS SAM application and the artifacts created by sam deploy.",
    "logs": "Fetch AWS Cloudwatch logs for AWS Lambda Functions or Cloudwatch Log groups.",
    "publish": "Publish a packaged AWS SAM template to AWS Serverless Application Repository for easy sharing.",
    "traces": "Fetch AWS X-Ray traces.",
    "sync": "Sync an AWS SAM project to AWS.",
    "pipeline": "Manage the continuous delivery of your AWS serverless application.",
    "list": "Fetch the state of your AWS serverless application.",
    "docs": "Launch the AWS SAM CLI documentation in a browser.",
}
