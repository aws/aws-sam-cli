Title: Template for design documents
====================================

What is the problem?
--------------------

There are cases when we need to mount extra volumes in a container with running lambda,
e.g. if you want to start a debugger and map an extra custom directory to collect debugger logs.
Currently, SAM CLI does not provide a way to mount an additional volumes in a container when running lambda 
in debug mode. The only one volume is mounted based on ``--debugger-path`` SAM CLI option. 

What will be changed?
---------------------

Extra option should be added to SAM CLI ``--additional-volume`` to mount additional volumes in a container.
The option can be added multiple times to map multiple volumes. A host directory existence is validated on SAM CLI level.

Success criteria for the change
-------------------------------

All valid directories specified through ``--additional-volume`` option are mounted in docker container
that is used to run/debug lambda.

Out-of-Scope
------------

User Experience Walkthrough
---------------------------

A User can specify one or multiple ``--additional-volume`` with SAM CLI ``local invoke`` method to setup directories mapping
between a container and a host. These additional volumes could be used to get access to logs that are produced
by external debugger.

Implementation
==============

CLI Changes
-----------

A new option is added to ``sam invoke`` calls - ``--aditional-volume``. 
The option can be used multiple times.

### Breaking Change

No breaking changes.

Design
------

SAM CLI API will be extended to a new option ``--additional-volume``.
Option details:
- Flags: ``multiple=True``
- Type: ``Path``:

  ``exists=True`` – check for host directory existence to skip validation on code level.
  ``file_okay=False`` – mount only directories.
  
All specified directories through ``--additional-volume`` option are mounted by the following rules: 
- volumes are mounted inside ``/tmp/lambci_volumes`` directory
- remote volume path is composed from ``/tmp/lambci_volumes`` + host directory base name, e.g.
  ``--additional-volume="/Users/user/dir_to_map"`` will be mapped to ``/tmp/lambci_volumes/dir_to_map`` inside a container.

`.samrc` Changes
----------------

No changes.

Security
--------

**What new dependencies (libraries/cli) does this change require?**
None.

**What other Docker container images are you using?**
None.

**Are you creating a new HTTP endpoint? If so explain how it will be
created & used**
No.

**Are you connecting to a remote API? If so explain how is this
connection secured**
No.

**Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?**
We are mapping a known host directory to a directory inside a container. This might be used to
collect logs that are produced by debugger when running SAM CLI in debug mode. 

**How do you validate new .samrc configuration?**

What is your Testing Plan (QA)?
===============================

Goal
----

Get access to a directory inside a container to be able to read files from a remote directory 
(e.g. read log files created by debugged). 

Pre-requesites
--------------

Test Scenarios/Cases
--------------------

1. SAM CLI invoke with no ``--additional-volume`` option specified.
2. Single valid ``--additional-volume`` option.
3. Multiple valid ``--additional-volume`` option.
4. Single and multiple invalid ``--additional-volume`` path.
5. Mount read-only host directory.

Expected Results
----------------

1. No additional volumes are mounted in container.
2. Single specified directory is mounted in a container.
3. All specified directories are mounted in a container.
4. Validation error on SAM CLI command invoke level.
5. Directory is mounted in a container. Client should care about access.

Pass/Fail
---------

Documentation Changes
=====================

None.

Open Issues
============
- [#1485](https://github.com/awslabs/aws-sam-cli/issues/1485)

Task Breakdown
==============

-   \[x\] Send a Pull Request with this design document
-   \[x\] Build the command line interface
-   \[ \] Build the underlying library
-   \[x\] Unit tests
-   \[x\] Functional Tests
-   \[ \] Integration tests
-   \[ \] Run all tests on Windows
-   \[x\] Update documentation
