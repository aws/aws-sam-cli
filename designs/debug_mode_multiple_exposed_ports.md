Title: Template for design documents
====================================

What is the problem?
--------------------
Currently, there is one port is exposed from Docker instance when running lambda in debug mode. 
This port is used to connect a debugger. In my case, I need two ports to be exposed due to Debugger 
implementation specific (the Debugger connect to two sockets to collect different information). 

What will be changed?
---------------------
SAM CLI has a ``--debug-port`` parameter that provide a port. This parameter is stored in DebugContext object.
``DebugContext`` should store an array of ports instead of a single port. This array should be transformed
into a map containing each stored port when passing to docker container arguments.

Success criteria for the change
-------------------------------
All ports specified via single or multiple ``--debug-port`` SAM CLI options should be exposed by docker container.

Out-of-Scope
------------

User Experience Walkthrough
---------------------------
From the user perspective, it should only provide an ability to specify multiple ``--debug-port`` options:
``--debug-port 5600 --debug-port 5601``

Implementation
==============

CLI Changes
-----------

SAM CLI provide an option to specify multiple ports ``--debug-port 5600 --debug-port 5601``.

### Breaking Change

No changes.

Design
------

Update ``--debug-port`` option to allow to use it multiple times in SAM CLI.
The option type should take only integer values. The value is stored in ``DebugContext``. 
This value should be converted into a map of ``{ container_port : host_port }``
that is passed to ``ports`` argument when creating a docker container.

`.samrc` Changes
----------------

No changes.

Security
--------

No changes.

**What new dependencies (libraries/cli) does this change require?**

**What other Docker container images are you using?**

**Are you creating a new HTTP endpoint? If so explain how it will be
created & used**

**Are you connecting to a remote API? If so explain how is this
connection secured**

**Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?**

**How do you validate new .samrc configuration?**

What is your Testing Plan (QA)?
===============================

Goal
----
Make sure SAM CLI users can specify multiple ports and those ports are exposed
after creating a docker container in debug mode:

``sam local invoke --template <path_to_template>/template.yaml --event <path_to_event>/event.json --debugger-path <path_to_debugger> --debug-port 5600 --debug-port 5601``

Pre-requesites
--------------
Running SAM CLI with debug mode.

Test Scenarios/Cases
--------------------
1. Single port is specified: ``--debug-port 5600``
2. Multiple ports are specified: ``--debug-port 5600 --debug-port 5601``
3. No ports specified: ``--debug-port ``
4. No ``--debug-port`` parameter is specified

Expected Results
----------------
1. Single port is exposed in docker container
2. All specified ports are exposed in docker container
3. No ports exposed.
4. No ports exposed.

Pass/Fail
---------

Documentation Changes
=====================

Open Issues
============
- [1463](https://github.com/awslabs/aws-sam-cli/issues/1463)

Task Breakdown
==============

-   \[x\] Send a Pull Request with this design document
-   \[ \] Build the command line interface
-   \[ \] Build the underlying library
-   \[x\] Unit tests
-   \[x\] Functional Tests
-   \[x\] Integration tests
-   \[ \] Run all tests on Windows
-   \[x\] Update documentation
