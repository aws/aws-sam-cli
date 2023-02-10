Title: Template for design documents
====================================

Use this as a template to write a design document when adding new
commands or major features to SAM CLI. It helps other developers
understand the scope of the project, validate technical complexity and
feasibility. It also serves as a public documentation of how the feature
actually works.

**Process:** 

1. Copy this template to another file in the `designs` folder.
2. Fill out the sections in the template.
3. Send a "Work In Progress" Pull Request with your design document. We can discuss the
designs in more detail and iterate on the requirements. Feel free to
start implementing a prototype if you think it will help flush out
design.
4. Once the PR is approved, create Github Issues for each task
listed in the document and start implementing them.

What is the problem?
--------------------

What will be changed?
---------------------

Success criteria for the change
-------------------------------

Out-of-Scope
------------

User Experience Walkthrough
---------------------------

Implementation
==============

CLI Changes
-----------

*Explain the changes to command line interface, including adding new
commands, modifying arguments etc*

### Breaking Change

*Are there any breaking changes to CLI interface? Explain*

Design
------

*Explain how this feature will be implemented. Highlight the components
of your implementation, relationships* *between components, constraints,
etc.*

``samconfig.toml`` Changes
----------------

*Explain the new configuration entries, if any, you want to add to
`samconfig.toml`*

Security
--------

*Tip: How does this change impact security? Answer the following
questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**

**What other Docker container images are you using?**

**Are you creating a new HTTP endpoint? If so explain how it will be
created & used**

**Are you connecting to a remote API? If so explain how is this
connection secured**

**Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?**

**How do you validate new `samconfig.toml` configuration?**

What is your Testing Plan (QA)?
===============================

Goal
----

Pre-requesites
--------------

Test Scenarios/Cases
--------------------

Expected Results
----------------

Pass/Fail
---------

Documentation Changes
=====================

Open Issues
============

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
