.. contents:: **Table of Contents**
   :depth: 2
   :local:

``sam publish`` command
====================================

This is the design for a command to publish an application to `AWS Serverless Application Repository (SAR)`_ with a SAM
template. It can be used to create a new application w/ its first version, update existing application's metadata, and
create new versions of the application.

.. _AWS Serverless Application Repository (SAR): https://aws.amazon.com/serverless/serverlessrepo/


What is the problem?
--------------------
To publish an app to AWS Serverless Application Repository, customers need to go through the following steps: first upload
the application code and SAM template to an Amazon S3 bucket, correctly set S3 bucket policy that grants the service read
permissions for artifacts uploaded to S3, then open the AWS Serverless Application Repository console and provide information
in a bunch of input boxes. If they use the AWS CLI, they need to pass all the information as parameters, and it's easy to make
a mistake while typing in the command line.


What will be changed?
---------------------
In this proposal, we will be providing a new command, ``sam publish``, which takes a SAM template as input and publishes
an application to AWS Serverless Application Repository using applicaiton metadata specified in the template. Customers
need to provide application metadata information in the template, then ``sam package`` will handle uploading local files to S3,
and ``sam publish`` will create the app in Serverless Application Repository.


Success criteria for the change
-------------------------------
#. Support all the following use cases:

   * Create new application w/ its first version in SAR using ``sam publish``
   * Create new version of existing SAR application using ``sam publish``
   * Update application metadata of existing SAR application using ``sam publish``

#. ``sam package`` command can upload local readme/license files to S3.


Out-of-Scope
------------
#. Manage application permissions while publishing the app.

#. Recursively publish nested apps in the template (SAR CreateApplication API doesn't support yet).

#. Run through CI/CD pipeline for the application before publishing.

#. Publish to other repositories besides SAR.

#. Recognize template changes and suggest version number.

#. Publish appication if ``AWS::ServerlessRepo::Application`` section is not found in the template's ``Metadata`` section.


User Experience Walkthrough
---------------------------

Assuming that customers have the following SAM template:

.. code-block:: yaml

    Metadata:
        AWS::ServerlessRepo::Application:
            Name: my-app
            Description: hello world
            Author: user1
            SpdxLicenseId: Apache-2.0
            LicenseUrl: ./LICENSE.txt
            ReadmeUrl: ./README.md
            Labels: ['tests']
            HomePageUrl: https://github.com/user1/my-app-project
            SemanticVersion: 0.0.1
            SourceCodeUrl: https://github.com/user1/my-app-project

    Resources:
        HelloWorldFunction:
            Type: AWS::Lambda::Function
            Properties:
              ...
              CodeUri: ./source-code1
              ...

Build Lambda source code
  Run ``sam build -t template.yaml -b ./build -o built-template.yaml`` to build all functions in the template and output
  a SAM template that can be run through the package command.

Package built artifacts and local file references
  Run ``sam package --template-file built-template.yaml --output-template-file packaged.yaml --s3-bucket my-bucket``
  to upload code artifacts, readme and license files to S3 and generate the packaged template.

Create new application in SAR
  Run ``sam publish -t ./packaged.yaml`` to publish a new application named my-app in SAR with the first version
  created as 0.0.1. The app will be created as private by default. SAM CLI prints application created message, metadata
  used to create application and link to the console details page.

  >>> sam publish -t ./packaged.yaml
  Publish Succeeded
  Created new application with the following metadata:
  {
    "Name": "my-app",
    "Description": "hello world",
    "Author": "user1",
    "SpdxLicenseId": "Apache-2.0",
    "LicenseUrl": "s3://test/LICENSE.txt",
    "ReadmeUrl": "s3://test/README.md",
    "Labels": ['tests'],
    "HomePageUrl": "https://github.com/user1/my-app-project",
    "SemanticVersion": "0.0.1",
    "SourceCodeUrl": "https://github.com/user1/my-app-project"
  }
  Click the link below to view your application in AWS console:
  https://console.aws.amazon.com/serverlessrepo/home?region=<region>#/published-applications/<arn>

Create new version of an existing SAR application
  Modify the existing template, change SemanticVersion to 0.0.2, and run ``sam publish -t ./packaged.yaml`` again.
  SAM CLI prints application metadata updated message, values of updated metadata and link to the console details page.

  >>> sam publish -t ./packaged.yaml
  Publish Succeeded
  The following metadata of application <id> has been updated:
  {
    "Author": "user1",
    "Description": "description",
    "ReadmeUrl": "s3://test/README.md",
    ...
    "SemanticVersion": "0.0.2",
    "SourceCodeUrl": "https://github.com/hello"
  }
  Click the link below to view your application in AWS console:
  https://console.aws.amazon.com/serverlessrepo/home?region=<region>#/published-applications/<arn>

  Alternatively, you can provide the new version number through the --semantic-version option without manually modifying
  the template. The command will publish a new application version using the specified value.

  >>> sam publish -t ./packaged.yaml --semantic-version 0.0.2

Update the metadata of an existing application without creating new version
  Keep SemanticVersion unchanged, then modify metadata fields like Description or ReadmeUrl, and run
  ``sam publish -t ./packaged.yaml``. SAM CLI prints application metadata updated message, values of updated
  metadata and link to the console details page.

  >>> sam publish -t ./packaged.yaml
  Publish Succeeded
  The following metadata of application <id> has been updated:
  {
    "Author": "qwang",
    "Description": "description",
    "ReadmeUrl": "s3://test/README.md"
    ...
  }
  Click the link below to view your application in AWS console:
  https://console.aws.amazon.com/serverlessrepo/home?region=<region>#/published-applications/<arn>

Once the application is published, other developers in your team or your organization will be able to deploy it with a few
clicks. If the application is shared publicly, the whole community will be able to find it by visiting the AWS Serverless
Application Repository `public site`_.

.. _public site: https://serverlessrepo.aws.amazon.com/applications


Implementation
==============

CLI Changes
-----------
*Explain the changes to command line interface, including adding new commands, modifying arguments etc*

1. Add a new top-level command called ``sam publish`` with the following help message.

.. code-block:: text

  Usage: sam publish [OPTIONS]

    Use this command to publish a packaged AWS SAM template to the AWS
    Serverless Application Repository to share within your team, across your
    organization, or with the community at large.

    This command expects the template's Metadata section to contain an
    AWS::ServerlessRepo::Application section with application metadata
    for publishing. For more details on this metadata section, see
    https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-template-publishing-applications.html

    Examples
    --------
    To publish an application
    $ sam publish -t packaged.yaml --region <region>

  Options:
    -t, --template PATH       AWS SAM template file  [default: template.[yaml|yml]]
    --semantic-version TEXT   Optional. The value provided here overrides SemanticVersion
                              in the template metadata.
    --profile TEXT            Select a specific profile from your credential file to
                              get AWS credentials.
    --region TEXT             Set the AWS Region of the service (e.g. us-east-1).
    --debug                   Turn on debug logging to print debug message generated
                              by SAM CLI.
    --help                    Show this message and exit.

2. Update ``sam package`` (``aws cloudformation package``) command to support uploading locally referenced readme and
license files to S3.

Breaking Change
~~~~~~~~~~~~~~~
*Are there any breaking changes to CLI interface? Explain*

N/A

Design
------
*Explain how this feature will be implemented. Highlight the components of your implementation, relationships*
*between components, constraints, etc.*

SAM CLI will read the packaged SAM template and pass it as string to `aws-serverlessrepo-python <https://github.com/awslabs/aws-serverlessrepo-python>`_
library. The algorithm for ``sam publish -t ./packaged.yaml`` looks like this:

.. code-block:: python

    from serverlessrepo import publish_application

    with open('./packaged.yaml', 'r') as f:
        template = f.read()
        result = publish_application(template)


``.samrc`` Changes
------------------
*Explain the new configuration entries, if any, you want to add to .samrc*

N/A

Security
--------

*Tip: How does this change impact security? Answer the following questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**

A new dependency `aws-serverlessrepo-python <https://github.com/awslabs/aws-serverlessrepo-python>`_ will be added to interact with SAR.

**What other Docker container images are you using?**

N/A

**Are you creating a new HTTP endpoint? If so explain how it will be created & used**

N/A

**Are you connecting to a remote API? If so explain how is this connection secured**

Will be connecting to boto3 serverlessrepo `create_application`_, `update_application`_, `create_application_version`_ APIs through
the `aws-serverlessrepo-python <https://github.com/awslabs/aws-serverlessrepo-python>`_ library. The connection is secured by requiring
AWS credentials and permissions for the target application.

.. _create_application : https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/serverlessrepo.html#ServerlessApplicationRepository.Client.create_application
.. _update_application : https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/serverlessrepo.html#ServerlessApplicationRepository.Client.update_application
.. _create_application_version: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/serverlessrepo.html#ServerlessApplicationRepository.Client.create_application_version


**Are you reading/writing to a temporary folder? If so, what is this used for and when do you clean up?**

N/A

**How do you validate new .samrc configuration?**

N/A

Documentation Changes
---------------------

1. Add "AWS::ServerlessRepo::Application" spec in `Publishing Applications`_ guide.

  - Can be added in `SAM specification`_ in the future.

2. Add ``ReadmeUrl`` and ``LicenseUrl`` in `aws cloudformation package`_ documentation.

3. Add ``sam publish`` in `AWS SAM CLI Command Reference`_, and explain the command, usage, examples, options.

4. Add a quick start guide "Publishing your application to AWS Serverless Application Repository" explaining how to use ``sam publish``.

.. _SAM specification: https://github.com/awslabs/serverless-application-model/blob/master/versions/2016-10-31.md
.. _Publishing Applications: https://docs.aws.amazon.com/serverlessrepo/latest/devguide/serverless-app-publishing-applications.html
.. _aws cloudformation package: https://docs.aws.amazon.com/cli/latest/reference/cloudformation/package.html
.. _AWS SAM CLI Command Reference: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html

Open Issues
-----------

N/A

Task Breakdown
--------------
- [x] Send a Pull Request with this design document
- [ ] Build the command line interface
- [ ] Build the underlying library
- [ ] Unit tests
- [ ] Integration tests
- [ ] Run all tests on Windows
- [ ] Update documentation
