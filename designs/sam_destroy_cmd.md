SAM Destroy Command
====================

This is the design for a command to **destroy** a CloudFormation stack.

What is the problem?
--------------------

Customers create CloudFormation stacks using `sam deploy`. After deploying the stacks, customers may have to delete
a stack to cleanup all of their resources and stacks because of stacks that landed in ROLLBACK_FAILED, 
rapid testing of development tasks, and removing defective code that may have a large security risk.

Currently, Customers would have to open up the CloudFormation console every time they have to delete, forcing them to leave the cli or use the `aws cloudformation` command. 
This worsens developer experience as it requires them to leave their sam workflow to find what they are looking for. 

 
What will be changed?
---------------------

In this proposal, we will be providing a new command, `sam destroy`, to
destroy CloudFormation stacks in the cloud. 
Customers will be able to view failures of the commands and other events directly inside the cli.


Success criteria for the change
-------------------------------
- Customers will be able to delete a stack in the cloud

Out-of-Scope
------------
- Deleting and cleaning up resources that cannot be deleted or are in DELETE_FAILED state

User Experience Walkthrough
---------------------------
Customers first uses sam deploy to deploy the SAM/CloudFormation stack to the cloud. 
Once the customer has finished using the stack, the customer will run `sam destroy --stack-name <STACK_NAME>` 
to destroy the stack.

Implementation
==============


CLI Changes
-----------


### Breaking Change

Changes are additive and will not break any existing functionality.

Design
------

Proposal
--------

`.samrc` Changes
----------------
There are no changes to .samrc

Security
--------

Documentation Changes
---------------------
The cli command documentation will be added to
 https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-command-reference.html

Open Issues
-----------
The github pr #1197 and Issue #789

Task Breakdown
--------------

-   \[ \] Send a Pull Request with this design document
-   \[ \] Build the command line interface
-   \[ \] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Update documentation
