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
The stack will be deleted with `cfn.delete_stack(StackName=stack_name, **args)`. 

To handle errors better, the code will first check if there is a valid aws account, the stack specified exists, and 
if any resources are in the state DELETE_FAILED they are specified in the retained_resources section.

The two other errors that are specially handled are TerminationProtection and AccessDeniedException.

TerminationProtection will be checked if termination protection is turned on and provide the following error message.

```sh
The stack {stack_name} has TerminationProtection turned on. Disable it on the aws console at 
https://us-west-1.console.aws.amazon.com/cloudformation/home \n or run aws 
cloudformation update-termination-protection --stack-name {stack_name} 
--no-enable-termination-protection 
```

AccessDeniedException will be checked if the user does not have the access to delete the CloudFormation stack.
```sh
The user account does not have access to delete the stack. Please add the permissions for the relevant resources and
account policies.
```

Customers that delete the stack may want to wait for the stack to be deleted before continuing. The following waiter
can be used to wait for the stack to be deleted.
```python
waiter = cfn.get_waiter('stack_delete_complete')   
delay = 15
waiter.wait(StackName=stack_name,
            WaiterConfig={
                'Delay': delay,
                'MaxAttemps': wait_time / delay
})

```

CLI Changes
-----------
```sh
Usage: sam destroy [OPTIONS] [ARGS]...

  The sam destroy command destroys a Cloudformation Stack.

  e.g. sam destroy -stack-name sam-app

Options:
  --stack-name TEXT            The name of the AWS CloudFormation stack you're
                               deploying to. If you specify an existing stack,
                               the command updates the stack. If you specify a
                               new stack, the command creates it.  [required]
  --retain-resources TEXT      For  stacks  in  the DELETE_FAILED state, a
                               list of resource logicalIDs that are associated
                               with the resources you want to retain.  During
                               deletion,  AWS  CloudFormation  deletes  the
                               stack but does not delete the retained
                               resources.Retaining resources is useful when
                               you  cannot  delete  a  resource,such as a non-
                               empty S3 bucket, but you want to delete the
                               stack.
  --role-arn TEXT              The Amazon Resource Name (ARN) of an AWS
                               Identity and Access Management (IAM) role that
                               AWS 
                               CloudFormation assumes to delete the
                               stack. AWS CloudFormation uses the role's
                               credentials to make 
                               calls on your behalf. If
                               you don't specify a value, AWS CloudFormation
                               uses the role  that was  
                               previously
                               associated with the stack. If no role is
                               available, AWS CloudFormation uses a temporary
                               session that is  generated  from your user
                               credentials.
  --client-request-token TEXT  A unique identifier for this DeleteStack
                               request. Specify this token
                               if you plan to
                               retry requests so that AWS CloudFormation knows
                               that
                               you're  not  attempting  to  delete  a
                               stack with the same name. You
                               might retry
                               DeleteStack requests to ensure that  AWS
                               CloudFormation
                               successfully received them.
                               Learn more at aws cloudformation destroy help
  -w, --wait                   Option to wait for Stack deletion
  --wait-time TEXT             The time to wait for stack to delete in
                               seconds. Used with --wait. The default is 5
                               minutes
  --debug                      Turn on debug logging to print debug message
                               generated by SAM CLI.
  -h, --help                   Show this message and exit.
```

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
