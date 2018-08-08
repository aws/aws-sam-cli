Getting started with SAM and the SAM CLI
========================================
The following sections introduce the Serverless Application Model (SAM) and the the tools available to implement it (SAM CLI):

What is SAM
===========
The AWS Serverless Application Model (AWS SAM) is a model to define serverless applications. AWS SAM is natively supported by AWS CloudFormation and defines simplified syntax for expressing serverless resources. The specification currently covers APIs, Lambda functions and Amazon DynamoDB tables. SAM is available under Apache 2.0 for AWS partners and customers to adopt and extend within their own toolsets.

What is SAM CLI
===============
Based on AWS SAM, SAM CLI is an AWS CLI tool that provides an environment for you to develop, test, and analyze your serverless applications locally before uploading them to the Lambda runtime. Whether you're developing on Linux, Mac, or Microsoft Windows, you can use SAM CLI to create a local testing environment that simulates the AWS runtime environment. The SAM CLI also allows faster, iterative development of your Lambda function code because there is no need to redeploy your application package to the AWS Lambda runtime.


Installing Docker
~~~~~~~~~~~~~~~~~

To use SAM CLI, you first need to install Docker, an open-source software container platform that allows you to build, manage and test applications, whether you're running on Linux, Mac or Windows. For more information and download instructions, see `Docker <https://www.docker.com/>`__.

Once you have Docker installed, SAM CLI automatically provides a customized Docker image called docker-lambda. This image is designed specifically by an AWS partner to simulate the live AWS Lambda execution environment. This environment includes installed software, libraries, security permissions, environment variables, and other features outlined at Lambda Execution Environment and Available Libraries.

Using docker-lambda, you can invoke your Lambda function locally. In this environment, your serverless applications execute and perform much as in the AWS Lambda runtime, without your having to redeploy the runtime. Their execution and performance in this environment reflect such considerations as timeouts and memory use.

  Important

  Because this is a simulated environment, there is no guarantee that your local testing results will exactly match those in the actual AWS runtime.
For more information, see `docker-lambda <https://github.com/lambci/docker-lambda>`__.

Installing SAM CLI
~~~~~~~~~~~~~~~~~~

The easiest way to install SAM CLI is to use `pip <https://pypi.org/project/pip/>`__.

.. code:: bash

    pip install aws-sam-cli

Then verify that the installation succeeded.

.. code:: bash

  sam --version

If pip doesn't work for you, you can download the latest binary and start using SAM CLI immediately. You can find the binaries under the Releases section in the `SAM CLI GitHub Repository <https://github.com/awslabs/aws-sam-local/releases>`__.

Creating a hello-world app (init)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To get started with a project in SAM, you can use the 'sam init' command provided by the SAM CLI to get a fully deployable boilerplate serverless application in any of the supported runtimes.  SAM init provides a quick way for customers to get started with creating a Lambda-based application and allow them to grow their idea into a production application by using other commands in the SAM CLI.

To use 'sam init', nagivate to a directory where where you want the serverless application to be created. Using the SAM CLI, run the following command (using the runtime of your choice. The following example uses Python for demonstration purposes.):

.. code::

  $ sam init --runtime python
  [+] Initializing project structure...
  [SUCCESS] - Read sam-app/README.md for further instructions on how to proceed
  [*] Project initialization is now complete
This will create a folder in the current directory titled sam-app. This folder will contain an `AWS  SAM template <https://github.com/awslabs/serverless-application-model>`__, along with your function code file and a README file that provides further guidance on how to proceed with your SAM application. The SAM template defines the AWS Resources that your application will need to run in the AWS Cloud.

Learn More
==========

-  `Project Overview <../README.rst>`__
-  `Installation <installation.rst>`__
-  `Usage <usage.rst>`__
-  `Packaging and deploying your application <deploying_serverless_applications.rst>`__
-  `Advanced <advanced_usage.rst>`__