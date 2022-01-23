Checksum on artifacts for `sam package`
====================================


What is the problem?
--------------------

Today, `sam package` goes through the list of packageable paths and looks up objects in s3 and compares checksums across local and whats in S3 (if they already exist). The comparison on `zip` files are prone to failure as the zipped file does not have respect permissions of the underlying directory which was zipped. Therefore the calculated checksums between local and S3 are different, resulting in re-upload when deploying an application repeatedly even with no changes in source.

Lets consider following cases:

NOTE: `sam deploy` attempts to package on deploy.

`sam build` -> `sam deploy` : Results in upload to s3
`sam build` -> `sam deploy` (s3 upload) -> `sam deploy` (s3 upload again on same built artifacts)

What will be changed?
---------------------

Instead of calculating checksum on a zip file, the checksum is calculated on the directory which is to be zipped up instead.

* Symlinks within the directory are followed.
* Cyclic symlinks cause failure to package.
* Both name and content of the files within the directory are used to calculate a checksum.

What algorithm is used for checksum calculation?
------------------------------------------------

* `md5`

Caveat: There are still chances for collision of hashes with `md5`, `sha256` may be better in this case, but the codebase has been using `md5` for a while and switching to `sha256` may cause regressions(?)

Success criteria for the change
-------------------------------

* `sam build` -> `sam deploy` -> `sam deploy` (Does not result in another deploy)
* `sam build` -> `sam deploy` -> `sam build` (No changes to source) -> `sam deploy` (Does not result in another deploy)

Out-of-Scope
------------

* This is a bug fix of the prior implementation.

User Experience Walkthrough
---------------------------

Implementation
==============

CLI Changes
-----------

- No changes to CLI parameters itself.

### Breaking Change

- The breaking change here is that users that relied on always `re-deploying` even with no changes to source made might be broken.

Design
------

- A new method called `dir_checksum` is written which will take a directory as input and give back a md5 checksum of all the contents within the directory.
 * Goes through all subdirectories and files
 * Checksums file names and contents of each file.

`samconfig.toml` Changes
----------------

None

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

N/A

**Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?**

No Temporary folders are read, but the contents of each file specified in a directory are read in order to determine md5 checksum.

**How do you validate new .samrc configuration?**

N/A

What is your Testing Plan (QA)?
===============================

Goal
----

* Integration and Unit tests pass

Pre-requesites
--------------

N/A

Test Scenarios/Cases
--------------------
* build and deploy an application, rebuild and attempt to deploy an application. The second deploy should not trigger.

Expected Results
----------------
* Scenario tests are successful


Documentation Changes
=====================

* Fixes an underlying bug, the documentation does not state that this is an issue today.

Open Issues
============

* https://github.com/awslabs/aws-sam-cli/issues/1779

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
