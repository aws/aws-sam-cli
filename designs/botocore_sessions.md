CLI: Botocore Sessions
====================================

What is the problem?
--------------------

SAM CLI does not have first class support for MFA based authentication, which leads to multiple requests for such tokens degrading the overall CLI experience.

What will be changed?
---------------------
* SAM CLI will support default sessions with caching of temporary credentials to a json cache.

Success criteria for the change
-------------------------------
* SAM CLI only ever asks for a MFA token once and caches it under the default boto location. This allows for other application that uses default location for caching credentials.

Out-of-Scope
------------

User Experience Walkthrough
---------------------------
* SAM CLI on the first interaction with any AWS resource using AWS credentials that support MFA credentials creates a prompt which says `Enter MFA Code: xxxxxxxxxxxxxx/xxxx`

Note: This MFA code is entered via a U2f/virtual mfa device/gemalto token.

Once the code is entered and successfully validated, this results in temporary caching of the credentials with an `sts` call.

Implementation
==============

CLI Changes
-----------

The only changes are during the setting up the boto3 session in the cli context, this propogates the boto3 session context all the way down across all sub commands of SAM CLI.


### Breaking Change
 
There are no breaking changes.

samconfig.toml Changes
----------------

There are no samconfig.toml changes.

Security
--------

**What new dependencies (libraries/cli) does this change require?**

N/A

**What other Docker container images are you using?**

N/A

**Are you creating a new HTTP endpoint? If so explain how it will be
created & used**

N/A

**Are you connecting to a remote API? If so explain how is this
connection secured**

* Connect to all aws endpoints, secured with aws credentials.

**Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?**

N/A

**How do you validate new .samrc configuration?**

N/A


What is your Testing Plan (QA)?
===============================

Goal
----

* All unit tests and integration tests pass.

Pre-requesites
--------------

* IAM user with MFA enabled.

Test Scenarios/Cases
--------------------

* Specific integration test case with a MFA prompt.

Expected Results
----------------
* No regressions

Documentation Changes
=====================

Open Issues
============
[1682](https://github.com/awslabs/aws-sam-cli/issues/1682)
[1623](https://github.com/awslabs/aws-sam-cli/issues/1623)

Task Breakdown
==============

-   \[x\] Send a Pull Request with this design document
-   \[ \] Build the command line interface
-   \[ \] Build the underlying library
-   \[ \] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Run all tests on Windows
-   \[ \] Update documentation
