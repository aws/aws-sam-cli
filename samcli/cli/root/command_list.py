"""
Data structure to host the root command name and short help text to speed up load time.
"""
SAM_CLI_COMMANDS = {
    "init": "Initialize an AWS SAM application.",
    "validate": "Validate an AWS SAM template.",
    "build": "Build your AWS serverless function code.",
    "local": "Run your AWS serverless function locally.",
    "package": "Package an AWS SAM application.",
    "deploy": "Deploy an AWS SAM application.",
    "delete": "Delete an AWS SAM application and the artifacts created by sam deploy.",
    "logs": "Fetch AWS Cloudwatch logs for a function.",
    "publish": "Publish a packaged AWS SAM template to AWS Serverless Application Repository for easy sharing.",
    "traces": "Fetch AWS X-Ray traces.",
    "sync": "Sync an AWS SAM project to AWS.",
    "pipeline": "Manage the continuous delivery of your AWS serverless application.",
    "list": "Fetch the state of your AWS serverless application.",
}
