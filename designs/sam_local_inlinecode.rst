.. contents:: **Table of Contents**
   :depth: 2
   :local:



``InlineCode`` debug
=====================
This is the design for a feature to provide local testing capabilities to functions defined via **InlineCode** key schema.

What is the problem?
--------------------
When new functions are started an absolute path of the folder/file containing AWS Lambda code package need to be passed
to docker deamon in order to bind-mount the path inside the container running the AWs Lambda runtime.

As of today you can only test locally your AWS Lambda Functions if defined via ``CodeUri`` key and not ``InlineCode``.
From now on we will use ``InlineCode`` to refer to both ``Serverless::Funnction`` and ``Lambda::Function`` inline code implementation (Where ``Code`` is used as the property).

What will be changed?
---------------------
In this proposal, we will change the code in a way that, if the tested AWS Lambda function is codified with
``InlineCode`` key, we will create a temporary local file based on the ``InlineCode`` value, passing the temp
file to bind-mount inside the container and make it possible to locally test ``InlineCode`` authored Functions.

Success criteria for the change
-------------------------------
#. Support all programming languages supported by ``InlineCode``

#. Local testing should just work for Functions authored with ``InlineCode``

Out-of-Scope
------------

#. Anything not specifically related to ``InlineCode`` and sam local commands
#. Provide support for Functions authored with ``InlineCode`` and leveraging ``!Sub`` pseudo function; in this case the local testing will fail
#. Provide explicit support for ``build`` action; that means you cannot build with sam when an ``InlineCode`` function is present in the template

User Experience Walkthrough
---------------------------


Implementation
==============

Design
------
*Explain how this feature will be implemented. Highlight the components of your implementation, relationships*
*between components, constraints, etc.*

Design should be pretty simple. Write a tempfile in ``./.aws-sam/build/<logical_id>`` and passing it to the Docker daemon as a bind-mount.
File is handled inside a context-manager and cleaned out after invocation.


Security
--------

*Tip: How does this change impact security? Answer the following questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**
None: InlineCode is handled transparently; no additional libraries are required beside python standard libraries

**Are you reading/writing to a temporary folder? If so, what is this used for and when do you clean up?**
Yes, I'm writing the ``InlineCode`` function string to a temporary file (inside the SAM project folder)
If cleanup need to be performed, a context manager solution should be adopted

Documentation Changes
---------------------
TBD

Open Issues
-----------

Task Breakdown
--------------
- [x] Send a Pull Request with this design document
- [ ] Build the required functions
- [ ] Hook functions in actual code
- [ ] Unit tests
- [ ] Functional Tests
- [ ] Integration tests
- [ ] Run all tests also on Windows
- [ ] Update documentation (if required)
