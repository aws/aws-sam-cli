SAM Deploy Command
====================

This is the design for a command to **deploy** a CloudFormation stack.

What is the problem?
--------------------

Customers create CloudFormation stacks using the `sam build` -> `sam package` -> `sam deploy` pipeline. However, after
deplyoing their stack, they recieve no aditional information about the stack, such as the status of the stacks and what is
happening around the stack without leaving the cli and going to the console.
This is because we are shelling out to the `aws cloudformation` instead of using boto3.
By using boto3, we have more control over the deploy operations and can make the developer experience to deploy easier


What will be changed?
---------------------

In this proposal, we will be providing an update to the command, `sam deploy`, to
allow for more control over the deploy calls and customizing the ux around it.
Customers will be able to view failures, status, events of the commands and other events directly inside the cli.


Success criteria for the change
-------------------------------
- Customers will be able to view the status of the events that they deploy to the cloud

Out-of-Scope
------------
- Providing diffs or interactive interfaces when deploying to the cloud

User Experience Walkthrough
---------------------------
Customers will first use sam package to package their built stack.
Then, Customers run sam deploy to deploy the SAM/CloudFormation stack to the cloud.
Then, the customer will be able to view the events that occurred while creating the stack.

Implementation
==============
The stack will be deleted with `cfn.create_stack(StackName=stack_name, **args)`.

To handle errors better, the code will first check if there is a valid aws account, wether stack specified already exists, and
log all events that are happening using `cfn.describe_stack_events`

The main errors that is specially handled AccessDeniedException.

AccessDeniedException will be checked if the user does not have the access to delete the CloudFormation stack.
```sh
The user account does not have access to create the stack. Please add the relevant permissions to create a stack.
```

We can wait for a healthy state using the following waiter
can be used to wait for the stack to be deleted.
```python
waiter = cfn.get_waiter('stack_create_complete')
delay = 15
waiter.wait(StackName=stack_name,
            WaiterConfig={
                'Delay': delay,
                'MaxAttemps': wait_time / delay
})

```

CLI Changes
-----------
There will be no CLI changes as the deploy command already exists.

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
Open Issues
-----------

Task Breakdown
--------------

-   \[ \] Send a Pull Request with this design document
-   \[ \] Build the command line interface
-   \[ \] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Update documentation
