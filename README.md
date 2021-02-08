<p align="center">
</p>

# AWS SAM

![Apache-2.0](https://img.shields.io/npm/l/aws-sam-local.svg)
![SAM CLI Version](https://img.shields.io/github/release/awslabs/aws-sam-cli.svg?label=CLI%20Version)

The AWS Serverless Application Model (SAM) is an open-source framework for building serverless applications. 
It provides shorthand syntax to express functions, APIs, databases, and event source mappings. 
With just a few lines of configuration, you can define the application you want and model it.

[![Getting Started with AWS SAM](./media/get-started-youtube.png)](https://www.youtube.com/watch?v=1dzihtC5LJ0)

![AWS SAM CLI help menu](https://user-images.githubusercontent.com/3770774/87969094-59d05a80-ca76-11ea-9c23-76306fa8592b.png)

## Get Started

To get started with building SAM-based applications, use the SAM CLI. SAM CLI provides a Lambda-like execution 
environment that lets you locally build, test, debug, and deploy applications defined by SAM templates.

* [Install SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
* [Build & Deploy a "Hello World" Web App](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-quick-start.html)
* [Install AWS Toolkit](https://aws.amazon.com/getting-started/tools-sdks/#IDE_and_IDE_Toolkits) to use SAM with your favorite IDEs.


**Next Steps:** Learn to build a more complex serverless application.
* [Extract text from images and store in a database](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-example-s3.html) using Amazon S3 and Amazon Rekognition services.
* [Detect when records are added to a database](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-example-ddb.html) using Amazon DynamoDB database and asynchronous stream processing.


**Detailed References:** Explains SAM commands and usage in depth.
* [CLI Commands](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html)
* [SAM Template Specification](https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md)
* [Policy Templates](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-policy-templates.html)

## Why SAM

+ **Single\-deployment configuration**\. SAM makes it easy to organize related components and resources, and operate on a single stack\. You can use SAM to share configuration \(such as memory and timeouts\) between resources, and deploy all related resources together as a single, versioned entity\.
   
+ **Local debugging and testing**\. Use SAM CLI to locally build, test, and debug SAM applications on a Lambda-like execution environment. It tightens the development loop by helping you find & troubleshoot issues locally that you might otherwise identify only after deploying to the cloud.

+ **Deep integration with development tools**. You can use SAM with a suite of tools you love and use.
    + IDEs: [PyCharm](https://aws.amazon.com/pycharm/), [IntelliJ](https://aws.amazon.com/intellij/), [Visual Studio Code](https://aws.amazon.com/visualstudiocode/), [Visual Studio](https://aws.amazon.com/visualstudio/), [AWS Cloud9](https://aws.amazon.com/cloud9/)
    + Build: [CodeBuild](https://docs.aws.amazon.com/codebuild/latest/userguide/)
    + Deploy: [CodeDeploy](https://docs.aws.amazon.com/codedeploy/latest/userguide/), [Jenkins](https://wiki.jenkins.io/display/JENKINS/AWS+SAM+Plugin)
    + Continuous Delivery Pipelines: [CodePipeline](https://docs.aws.amazon.com/codepipeline/latest/userguide/) 
    + Discover Serverless Apps & Patterns: [AWS Serverless Application Repository](https://docs.aws.amazon.com/serverlessrepo/latest/devguide/)

+ **Built\-in best practices**\. You can use SAM to define and deploy your infrastructure as configuration. This makes it possible for you to use and enforce best practices through code reviews. Also, with a few lines of configuration, you can enable safe deployments through CodeDeploy, and can enable tracing using AWS X\-Ray\.

+ **Extension of AWS CloudFormation**\. Because SAM is an extension of AWS CloudFormation, you get the reliable deployment capabilities of AWS CloudFormation\. You can define resources by using CloudFormation in your SAM template\. Also, you can use the full suite of resources, intrinsic functions, and other template features that are available in CloudFormation\.

## What is this Github repository? 💻
This Github Repository contains source code for SAM CLI. Here is the development team talking about this code:

> SAM CLI code is written in Python. Source code is well documented, very modular, with 95% unit test coverage. 
It uses this awesome Python library called Click to manage the command line interaction and uses Docker to run Lambda functions locally.
We think you'll like the code base. Clone it and run `make pr`!

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



