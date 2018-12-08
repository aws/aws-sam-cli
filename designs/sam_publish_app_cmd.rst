.. contents:: **Table of Contents**
   :depth: 2
   :local:

``sam publish app`` command
====================================

This is the design for a command to publish an application to `AWS Serverless Application Repository (SAR)`_ with a SAM
template. It can be used to create a new application and its first version, update exisitng application's metadata, create
a new version of the application, and manage application permissions.

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
In this proposal, we will be providing a new command, ``sam publish app``, which takes a SAM template as input and publishes
an application to AWS Serverless Application Repository using applicaiton metadata specified in the template. Customers
need to provide application metadata information in the template, then ``sam package`` will handle uploading local files to S3,
and ``sam publish app`` will create the app in Serverless Application Repository. We will also provide sharing options to set
application permission policies.


Success criteria for the change
-------------------------------
#. Support all the following use cases:

   * Create new application and its first version in SAR using ``sam publish app``
   * Create new version of existing SAR application using ``sam publish app``
   * Update application metadata of existing SAR application using ``sam publish app``
   * Share the app publicly using the ``--make-public`` option
   * Make the app private using the ``--make-private`` option
   * Share the app privately with other AWS accounts using the ``--account-ids`` option


#. ``sam package`` command can upload local readme/license files to S3.


Out-of-Scope
------------
#. Manage application permission separately without publishing/updating the app.

#. Specify granular `application permission`_ types when sharing the application. If needed, customers can use AWS CLI instead as described `here`_.

#. Recursively publish nested apps in the template (SAR CreateApplication API doesn't support yet).

#. Run through CI/CD pipeline for the application before publishing.

#. Publish to other repositories besides SAR.

#. Recognize template changes and suggest version number.

#. Publish appication if ``AWS::ServerlessRepo::Application`` section is not found in the template's ``Metadata`` section.

.. _application permission: https://docs.aws.amazon.com/serverlessrepo/latest/devguide/access-control-resource-based.html#application-permissions
.. _here: https://docs.aws.amazon.com/serverlessrepo/latest/devguide/access-control-resource-based.html#access-control-resource-based-example-multiple-permissions


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
            HomepageUrl: https://github.com/user1/my-app-project
            SemanticVersion: 1.0.0
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
  Run ``sam publish app -t ./packaged.yaml`` to publish a new application named my-app in SAR with the first version
  created as 1.0.0. The app will be created as private by default. SAM CLI prints application created message and
  link to the console details page.

Create new version of an existing SAR application
  Modify the existing template, give a different SemanticVersion value, and run ``sam publish app -t ./packaged.yaml``.
  SAM CLI prints application metadata updated message, application version created message, values of the current application
  metadata and link to the console details page.

Create application/version and set application permission
  Run ``sam publish app -t ./packaged.yaml --make-public`` to publish the app and share it publicly so that everyone is
  allowed to `Deploy`_ the app. Alternatively, use ``--account-ids <account ids>`` to share with some AWS accounts. Only
  you and the shared accounts can deploy the app.

  Customers can also revoke granted permissions and set the application back to be private, so it can
  only be deployed by the owning account: ``sam publish app -t ./packaged.yaml --make-private``

Update the metadata of an exsiting application without creating new version
  Keep SemanticVersion unchanged, then modify metadata fields like Description or ReadmeUrl, and run
  ``sam publish app -t ./packaged.yaml``. SAM CLI prints application metadata updated message, values of the current
  application metadata and link to the console details page.

Output of the ``sam publish app`` command will be a link to the AWS Serverless Application Repository console details page
of the app just published, message informing application created or application metadata updated w/ new application version
created, and the metadata fields that have been updated.

Once the application is published, other developers in your team or your organization will be able to deploy it with a few
clicks. If the application is shared publicly, the whole community will be able to find it by visiting the AWS Serverless
Application Repository `public site`_.

.. _Deploy: https://docs.aws.amazon.com/serverlessrepo/latest/devguide/access-control-resource-based.html#application-permissions
.. _public site: https://serverlessrepo.aws.amazon.com/applications


Implementation
==============

CLI Changes
-----------
*Explain the changes to command line interface, including adding new commands, modifying arguments etc*

1. Add a new top-level command called ``sam publish app`` with the following help message.

.. code-block:: text

  Usage: samdev publish app [OPTIONS]

    Use this command to publish a packaged AWS SAM template to the AWS
    Serverless Application Repository to share within your team, across your
    organization, or with the community at large.

    This command expects the template's Metadata section to contain an
    AWS::ServerlessRepo::Application section with application metadata
    for publishing. For more details on this metadata section, see
    https://docs.aws.amazon.com/serverlessrepo/latest/devguide/serverless-app-publishing-applications.html

  Options:
    -t, --template PATH  AWS SAM template file  [default: template.[yaml|yml]]
    --make-public        Share the app publicly with anyone.
    --make-private       Share the app only with the owning account.
    --account-ids TEXT   Share the app privately with the given comma-separated
                        list of AWS account ids.
    --profile TEXT       Select a specific profile from your credential file to
                        get AWS credentials.
    --region TEXT        Set the AWS Region of the service (e.g. us-east-1).
    --debug              Turn on debug logging to print debug message generated
                        by SAM CLI.
    --help               Show this message and exit.

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
library. The algorithm for ``sam publish app -t ./packaged.yaml --make-public`` looks like this:

.. code-block:: python

    from serverlessrepo import publish_application, make_application_public

    with open('./packaged.yaml', 'r') as f:
        template = f.read()
        result = publish_application(template)
        make_application_public(result.applicaiton_id)


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

Will be connecting to boto3 serverlessrepo `create_application`_, `update_application`_, `create_application_version`_, and `put_application_policy`_
APIs through the `aws-serverlessrepo-python <https://github.com/awslabs/aws-serverlessrepo-python>`_ library. The connection is secured by requiring
AWS credentials and permissions for the target application.

.. _create_application : https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/serverlessrepo.html#ServerlessApplicationRepository.Client.create_application
.. _update_application : https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/serverlessrepo.html#ServerlessApplicationRepository.Client.update_application
.. _create_application_version: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/serverlessrepo.html#ServerlessApplicationRepository.Client.create_application_version
.. _put_application_policy: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/serverlessrepo.html#ServerlessApplicationRepository.Client.put_application_policy


**Are you reading/writing to a temporary folder? If so, what is this used for and when do you clean up?**

N/A

**How do you validate new .samrc configuration?**

N/A

Documentation Changes
---------------------

#. Add "AWS::ServerlessRepo::Application" sepc in `Publishing Applications`_ guide and document how to use ``sam publish app``.

#. Add ``ReadmeUrl`` and ``LicenseUrl`` in `aws cloudformation package`_ documentation.

#. Add ``sam publish app`` in `AWS SAM CLI Command Reference`_, and explain the command, usage, examples, options.

#. Add a quick start guide "Publishing your application to AWS Serverless Application Repository" under SAM CLI `Get Started`_.

.. _Publishing Applications: https://docs.aws.amazon.com/serverlessrepo/latest/devguide/serverless-app-publishing-applications.html
.. _aws cloudformation package: https://docs.aws.amazon.com/cli/latest/reference/cloudformation/package.html
.. _AWS SAM CLI Command Reference: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html
.. _Get Started: https://github.com/awslabs/aws-sam-cli#get-started

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
