<p align="center">
</p>

# AWS SAM CLI

![Apache-2.0](https://img.shields.io/npm/l/aws-sam-local.svg)
![SAM CLI Version](https://img.shields.io/github/release/awslabs/aws-sam-cli.svg?label=CLI%20Version)
![Install](https://img.shields.io/badge/brew-aws--sam--cli-orange)
![pip](https://img.shields.io/badge/pip-aws--sam--cli-9cf)

[Installation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) | [Blogs](https://serverlessland.com/blog?tag=AWS%20SAM) | [Videos](https://serverlessland.com/video?tag=AWS%20SAM) | [AWS Docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html) | [Roadmap](https://github.com/aws/aws-sam-cli/wiki/SAM-CLI-Roadmap) | [Try It Out](https://s12d.com/Tq9ZE-Br)

The AWS Serverless Application Model (SAM) CLI is an open-source CLI tool that helps you develop serverless applications containing [Lambda functions](https://aws.amazon.com/lambda/), [Step Functions](https://aws.amazon.com/step-functions/), [API Gateway](https://aws.amazon.com/api-gateway/), [EventBridge](https://aws.amazon.com/eventbridge/), [SQS](https://aws.amazon.com/sqs/), [SNS](https://aws.amazon.com/sns/) and more. Some of the features it provides are:
- **Initialize serverless applications** in minutes with AWS provided infrastructure templates with `sam init`
- **Compile, build, and package** Lambda functions with provided runtimes and with custom Makefile workflows, for zip and image types of Lambda functions with `sam build`
- **Locally test** a Lambda function and API Gateway easily in a Docker container with `sam local` commands on SAM and CDK applications
- **Sync and test your changes in the cloud** with `sam sync` in your developer environments
- **Deploy** your SAM and CloudFormation templates using `sam deploy`
- Quickly **create pipelines** with prebuilt templates with popular CI/CD systems using `sam pipeline init`
- **Tail CloudWatch logs and X-Ray traces** with `sam log` and `sam trace`


## Get Started

To get started with building SAM-based applications, use the SAM CLI. SAM CLI provides a Lambda-like execution 
environment that lets you locally build, test, debug, and deploy [AWS serverless](https://aws.amazon.com/serverless/) applications.

* [Install SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
* [Build & Deploy a "Hello World" Web App](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-quick-start.html)
* [Install AWS Toolkit](https://aws.amazon.com/getting-started/tools-sdks/#IDE_and_IDE_Toolkits) to use SAM with your favorite IDEs
* [Tutorials and Workshops](https://serverlessland.com/learn)
* [Lambda Powertools](https://aws.amazon.com/blogs/opensource/simplifying-serverless-best-practices-with-lambda-powertools/) Utilities for building Lambda functions in [Python](https://awslabs.github.io/aws-lambda-powertools-python/latest/), [Java](https://github.com/awslabs/aws-lambda-powertools-java), and [TypeScript](https://github.com/awslabs/aws-lambda-powertools-typescript)


**Next Steps:** Learn to build a more complex serverless application.
* [Extract text from images and store in a database](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-example-s3.html) using Amazon S3 and Amazon Rekognition services.
* [Detect when records are added to a database](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-example-ddb.html) using Amazon DynamoDB database and asynchronous stream processing.
* [Explore popular patterns](https://serverlessland.com/patterns)


## What is this Github repository? 💻
This Github Repository contains source code for SAM CLI. Here is the development team talking about this code:

> SAM CLI code is written in Python. Source code is well documented, very modular, with 95% unit test coverage. 
It uses this awesome Python library called Click to manage the command line interaction and uses Docker to run Lambda functions locally.
We think you'll like the code base. Clone it and run `make pr` or `./Make -pr` on Windows!


## Related Repositories and Resources
+ **SAM Transform** [Open source template specification](https://github.com/awslabs/serverless-application-model/) that provides shorthand syntax for CloudFormation
+ **SAM CLI application templates** Get started quickly with [predefined application templates](https://github.com/aws/aws-sam-cli-app-templates/blob/master/README.md) for all supported runtimes and languages, used by `sam init`
+ **Lambda Builders** [Lambda builder tools](https://github.com/aws/aws-lambda-builders) for supported runtimes and custom build workflows, used by `sam build`
+ **Build and local emulation images for CI/CD tools** [Build container images](https://gallery.ecr.aws/sam/) to use with CI/CD tasks 


## Contribute to SAM

We love our contributors ❤️ We have over 100 contributors who have built various parts of the product. 
Read this [testimonial from @ndobryanskyy](https://www.lohika.com/aws-sam-my-exciting-first-open-source-experience/) to learn
more about what it was like contributing to SAM. 

Depending on your interest and skill, you can help build the different parts of the SAM project; 

**Enhance the SAM Specification**

Make pull requests, report bugs, and share ideas to improve the full SAM template specification.
Source code is located on Github at [awslabs/serverless-application-model](https://github.com/awslabs/serverless-application-model). 
Read the [SAM Specification Contributing Guide](https://github.com/awslabs/serverless-application-model/blob/master/CONTRIBUTING.md)
to get started.
    
**Strengthen SAM CLI**

Add new commands or enhance existing ones, report bugs, or request new features for the SAM CLI.
Source code is located on Github at [awslabs/aws-sam-cli](https://github.com/awslabs/aws-sam-cli). Read the [SAM CLI Contributing Guide](https://github.com/awslabs/aws-sam-cli/blob/develop/CONTRIBUTING.md) to 
get started. 

**Update SAM Developer Guide**

[SAM Developer Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/index.html) provides comprehensive getting started guide and reference documentation.
Source code is located on Github at [awsdocs/aws-sam-developer-guide](https://github.com/awsdocs/aws-sam-developer-guide).
Read the [SAM Documentation Contribution Guide](https://github.com/awsdocs/aws-sam-developer-guide/blob/master/CONTRIBUTING.md) to get
started. 

### Join the SAM Community on Slack
[Join the SAM developers channel (#samdev)](https://join.slack.com/t/awsdevelopers/shared_invite/zt-idww18e8-Z1kXhI7GNuDewkweCF3YjA) on Slack to collaborate with fellow community members and the AWS SAM team.

