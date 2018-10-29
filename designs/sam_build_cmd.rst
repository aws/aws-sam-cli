``sam build`` command
=====================
This is the design for a command to **build** a Lambda function. **Build** is the operation of converting the function's
source code to an artifact that can be executed on AWS Lambda.


What is the problem?
--------------------
To run a function on AWS Lambda, customers need to provide a zip file containing an executable form of the code. The
process of creating the executable usually involves downloading dependent libraries, optionally compiling the code
on Amazon Linux, copying static assets, and arranging the files in a directory structure that AWS Lambda accepts.
In some programming languages like Javascript, this process is fairly straightforward (just zip a folder), and in
others like Python, it is much involved.

Customers using SAM CLI can easily create Lambda function code (using ``sam init``) and package their artifact as a
zip file (using ``sam package``), but they have to handle the build process themselves. Customers usually implement
their own build scripts or adopt other's scripts from the internet. This is where many customers fall off the cliff.


What will be changed?
---------------------
In this proposal, we will be providing a new command,``sam build``, to build Lambda functions for all programming
languages that AWS Lambda supports. The cardinality of the problem is number of programming languages (N) times the
number of package managers (M) per language. Hence is it is nearly impossible to natively support each combination.
Instead, ``sam build`` will support an opinionated set of package managers for all programming languages. We will
provide an option for customers to bring their own build scripts or override the default for any programming language.
SAM CLI will still take care of the grunt work of iterating through every function in the SAM template, figuring out
the source code location, creating temporary folders to store built artifacts, running the build command and
move artifacts to right location.


Success criteria for the change
-------------------------------
#. Support all programming languages supported by AWS Lambda

   * Nodejs with NPM
   * Java with Maven
   * Python with PIP
   * Golang with Go CLI
   * Dotnetcore with DotNet CLI


#. Each Lambda function in SAM template gets built

#. Produce stable builds (best effort): If the source files did not change, built artifacts should not change.

#. Built artifacts should "just work" with ``sam local`` and ``sam package`` suite of commands

#. Ability to provide arbitrary build scripts for each Lambda Function runtime. This will either override the built-in
   default or add build support for languages/tools that SAM CLI does not support (ex: java+gradle).

#. Opt-in to building native dependencies that can run on AWS Lambda using Docker.

#. Support one dependency manifest (ex: package.json) entire app or one per each Lambda function.

#. Support out-of-source builds: ie. source code of Lambda function is outside the directory containing SAM template.


Out-of-Scope
------------
#. Supports adding data files ie. files that are not referenced by the package manager (ex: images, css etc)
#. Support to exclude certain files from the built artifact (ex: using .gitignore or using regex)
#. Integrate build action with ``sam local/package/deploy`` commands so the Lambda functions will be automatically
   built as part of the command without explicitly running the build command.
#. If the app contains a ``buildspec.yaml``, automatically run it using CodeBuild Local.
#. Watch for file changes and build automatically (ex: ``sam build --watch``)
#. Support other build systems by default Webpack, Yarn or Gradle.
#. Support in AWS CLI, ``aws cloudformation``, suite of commands
#. Support for fine-grained hooks (ex: hooks that run pre-build, post-build, etc)

User Experience
---------------


Implementation
==============

CLI Changes
-----------
*Explain the changes to command line interface, including adding new commands, modifying arguments etc*

Breaking Change
~~~~~~~~~~~~~~~
*Are there any breaking changes to CLI interface? Explain*

Design
------
*Explain how this feature will be implemented. Highlight the components of your implementation, relationships*
*between components, constraints, etc.*



``.samrc`` Changes
------------------
*Explain the new configuration entries, if any, you want to add to .samrc*


Security
--------

*Tip: How does this change impact security? Answer the following questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**

**What other Docker container images are you using?**

**Are you creating a new HTTP endpoint? If so explain how it will be created & used**

**Are you connecting to a remote API? If so explain how is this connection secured**

**Are you reading/writing to a temporary folder? If so, what is this used for and when do you clean up?**

**How do you validate new .samrc configuration?**


Documentation Changes
---------------------

Open Issues
-----------

Task Breakdown
--------------
- [x] Send a Pull Request with this design document (PR #123)
- [ ] Build the command line interface (Issue #124)
- [ ] Build the underlying library (Issue #125)
- [ ] Unit tests
- [ ] Functional Tests
- [ ] Integration tests
- [ ] Run all tests on Windows
- [ ] Update documentation
