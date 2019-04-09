SAM Build producing debuggable artifacts
========================================

What is the problem?
--------------------

`sam build` produces artifacts that are built for production use. In some langauges (usually interpreted), 
these production artifacts are also debuggable locally. In the case of compiled languages, you usually need to compile
the binary or artifact in a specific manner for them to be debuggable.  

What will be changed?
---------------------

We will introduce a way in `sam build` to produce these debuggable artifacts for those compiled languages.

Success criteria for the change
-------------------------------

1. Artifacts generated will be debuggable for runtimes DotNetCore 2.0 and above. 

Out-of-Scope
------------

1. Other languages `sam build` supports will not be changed

User Experience Walkthrough
---------------------------

Implementation
==============

CLI Changes
-----------

*Explain the changes to command line interface, including adding new
commands, modifying arguments etc*

### Breaking Change

Changes are additive and will not break any existing functionality.

Design
------

Options considered
------------------
We have a couple options to consider:

1. A command line option (`--mode`)
    * Pros
        * Customer can control what kind of artifacts are produced.
        * There is no guessing needed by the CLI
    * Cons
        * Yet another option for customers to learn or know about
        * Makes the customer need to think about the artifacts they need to produce (though this can be hidden
        behind the AWS Toolkit in IDEs)
        * Customers running in the command line need to remember what artifacts to produce or what they previously produced
2. An Environment Variable we read (`SAM_BUILD_MODE`). IDE Toolkit will set the env var when calling `sam build`
while debugging.
    * Pros
        * Reduces cognitive load on customers that don't care about debugging dotnet apps through command line.
        * Could force customers to use AWS Toolkit by default
    * Cons
        * Building debug artifacts becomes a hidden feature (silent contract)
        * Environment Variables tend to be more set and forget.
        * Need to conditionally add Env Var instead of a more convenient flag
3. Seamless Integration: `sam build` produces debug artifacts by default and `sam package` will build 
non debug artifacts by default
    * Pros
        * Customers should never have to think about 'when to produce debug artifacts' or forget to add a flag
    * Cons
        * Requires additional work on package to auto build.
        * Breaks what is produced from `sam build` as build is positioned to produce artifacts that are ready for deployment

Proposal
--------

My recommendation is to follow Option #2 from above, mainly because:

- Seamless Integration (#3) is best experience but is large in scope.
- CLI Option (#1) exposes a flag for what we think will be a rarely used CLI feature. We think so because manually 
setting up debugging is cumbersome. Given that .NET developers generally prefer to be within the IDE, I find it hard 
to believe someone will want to go out of the way of setting it up through CLI.
- Not a one-way-door. We can always add a CLI option to pair with env var later.

`.samrc` Changes
----------------

*Explain the new configuration entries, if any, you want to add to
.samrc*

Security
--------

*Tip: How does this change impact security? Answer the following
questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**
No

**What other Docker container images are you using?**
N/A

**Are you creating a new HTTP endpoint? If so explain how it will be
created & used**
No

**Are you connecting to a remote API? If so explain how is this
connection secured**
No

**Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?**
No

**How do you validate new .samrc configuration?**
N/A

Documentation Changes
---------------------

Open Issues
-----------

Task Breakdown
--------------

-   \[x\] Send a Pull Request with this design document
-   \[ \] Build the command line interface
-   \[ \] Build the underlying library
-   \[ \] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Run all tests on Windows
-   \[ \] Update documentation
