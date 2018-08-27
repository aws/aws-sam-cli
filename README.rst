.. raw:: html

   <p align="center">

.. raw:: html

   </p>

==============
SAM CLI (Beta)
==============

|Build Status| |Apache-2.0| |Contributers| |GitHub-release| |PyPI version|

`Join the SAM developers channel (#samdev) on
Slack <https://awssamopensource.splashthat.com/>`__ to collaborate with
fellow community members and the AWS SAM team.

``sam`` is the AWS CLI tool for managing Serverless applications
written with `AWS Serverless Application Model
(SAM) <https://github.com/awslabs/serverless-application-model>`__. SAM
CLI can be used to test functions locally, start a local API Gateway
from a SAM template, validate a SAM template, fetch logs, generate sample payloads
for various event sources, and generate a SAM project in your favorite
Lambda Runtime.



Main features
-------------

-  Develop and test your Lambda functions locally with ``sam local`` and
   Docker
-  Invoke functions from known event sources such as Amazon S3, Amazon
   DynamoDB, Amazon Kinesis Streams, etc.
-  Start local API Gateway from a SAM template, and quickly iterate over
   your functions with hot-reloading
-  Validate SAM templates
-  Get started with boilerplate Serverless Service in your chosen Lambda
   Runtime ``sam init``


Get Started
-----------

Learn how to get started using the SAM CLI with these guides:

-  `Installation <docs/installation.rst>`__: Set up your MacOs, Linux or Windows Machine to run serverless projects with SAM CLI.
-  `Introduction to SAM and SAM CLI <docs/getting_started.rst>`__ What is SAM and SAM CLI, and how can you use it to make a simple hello-world app.
-  `Running and debugging serverless applications locally <docs/usage.rst>`__: Describes how to use SAM CLI for invoking Lambda functions locally, running automated tests, fetching logs, and debugging applications
-  `Packaging and deploying your application <docs/deploying_serverless_applications.rst>`__: Deploy your local application using an S3 bucket, and AWS CloudFormation.
-  `Advanced <docs/advanced_usage.rst>`__: Learn how to work with compiled languages (such as Java and .NET), configure IAM credentials, provide environment variables, and more.
-  `Examples <#examples>`__


Project Status
--------------

-  [ ] Python Versions support

   -  [x] Python 2.7
   -  [x] Python 3.6

-  [ ] Supported AWS Lambda Runtimes

   -  [x] ``nodejs``
   -  [x] ``nodejs4.3``
   -  [x] ``nodejs6.10``
   -  [x] ``nodejs8.10``
   -  [x] ``java8``
   -  [x] ``python2.7``
   -  [x] ``python3.6``
   -  [x] ``go1.x``
   -  [ ] ``dotnetcore1.0``
   -  [x] ``dotnetcore2.0``
   -  [x] ``dotnetcore2.1``

-  [x] AWS credential support
-  [x] Debugging support
-  [x] Inline Swagger support within SAM templates
-  [x] Validating SAM templates locally
-  [x] Generating boilerplate templates

   -  [x] ``nodejs``
   -  [x] ``nodejs4.3``
   -  [x] ``nodejs6.10``
   -  [x] ``nodejs8.10``
   -  [x] ``java8``
   -  [x] ``python2.7``
   -  [x] ``python3.6``
   -  [x] ``go1.x``
   -  [x] ``dotnetcore1.0``
   -  [x] ``dotnetcore2.0``

Contributing
------------

Contributions and feedback are welcome! Proposals and pull requests will
be considered and responded to. For more information, see the
`CONTRIBUTING <CONTRIBUTING.md>`__ file.

A special thank you
-------------------

SAM CLI uses the open source
`docker-lambda <https://github.com/lambci/docker-lambda>`__ Docker
images created by `@mhart <https://github.com/mhart>`__.


.. raw:: html

   <!-- Links -->

.. |Build Status| image:: https://travis-ci.org/awslabs/aws-sam-cli.svg?branch=develop
.. |Apache-2.0| image:: https://img.shields.io/npm/l/aws-sam-local.svg?maxAge=2592000
.. |Contributers| image:: https://img.shields.io/github/contributors/awslabs/aws-sam-cli.svg?maxAge=2592000
.. |GitHub-release| image:: https://img.shields.io/github/release/awslabs/aws-sam-cli.svg?maxAge=2592000
.. |PyPI version| image:: https://badge.fury.io/py/aws-sam-cli.svg

=======
