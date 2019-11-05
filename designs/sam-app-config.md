SAM CLI App Level Config
====================================


What is the problem?
--------------------

Today users of SAM CLI need to invoke the CLI directly with all parameters supplied to its commands.

for e.g: `sam build --use-container --debug`

But often, during the lifecycle of building and deploying a serverless application. the same commands get run repeatedly to build, package and deploy, before solidifying into the final application. 

These CLI commands are often long and have many changing parts.

Have a look at the following series of workflows


* `sam build --use-container --template ... --parameter-overrides=... --skip-pull-image --manifest ...`

* `sam package --s3-bucket ... --template-file ... --output-template-file ... --s3-prefix ... --kms-key-id ...`

* `sam deploy deploy --template-file ... --stack-name ... --capabilities ... --tags ... --parameter-overrides ... --kms-key-id ...`

If this could be condensed into a series of workflows that look like

* `sam build`
* `sam package`
* `sam deploy`

That would be a huge user experience win.

What will be changed?
---------------------

The suite of commands supported by SAM CLI would be aided by looking for a configuration file thats locally located to the template.yaml by default. 

`.aws-sam/sam-app-config`

This configuration would solely be used for specifiying the parameters that each of SAM CLI commands use and would be in TOML format.

A configuration file can also optionally be specified by each of the commands themselves as well.

`sam build --config .aws-sam/sam-app-dev-config`

Sample configuration file

```
[build]
profile="srirammv"
debug=true
skip_pull_image=true
use_container=true

[package]
profile="srirammv"
region="us-east-1"
s3_bucket="sam-bucket"
output_template_file="packaged.yaml"

[deploy]
template_file="packaged.yaml"
stack_name="using_config_file"
capabilities="CAPABILITY_IAM"
region="us-east-1"
profile="srirammv"
```

Success criteria for the change
-------------------------------

* Resolution of command line parameters should always favor explicit versus implicit. A native command line parameter specified directly on the command line should override a parameter specified in the configuration file.


Out-of-Scope
------------

* Not focusing on a global configuration. SAM CLI already has a notion of a global config at `~/.aws-sam/metadata.json`

User Experience Walkthrough
---------------------------

Once a configuration file is appropriately populated, day to day workflows per application developed with SAM CLI become much simpler.

* `sam build` -> `sam package` -> `sam deploy`
* `sam build` -> `sam local invoke`
* `sam build` -> `sam package` -> `sam publish`

Implementation
==============

CLI Changes
-----------

New command line argument is added per command called `--config` to be able to specify non default locations of config files

For example:

`sam build --config /tmp/sam-api-app-config`

### Breaking Change

* No breaking changes to the CLI, in absence of the configuration file, CLI continues to work as normal.

Design
------

*Explain how this feature will be implemented. Highlight the components
of your implementation, relationships* *between components, constraints,
etc.*

A custom decorator to `click.option` is developed which reads from a configuration file the sections that are pertinent to that particular command and populates the click's `map` context.

The configuration file parser is a custom provider that can be made to understand any configuration file format in a pluggable manner.

This decorator benefits from the same type checking that some SAM CLI parameters already use.

`.samrc` Changes
----------------

This design emphasizes parameter pass throughs with a configuration file and does not change the core working of the SAM CLI itself. The SAM CLI continues to be working just as it was with efficiency gains in usability.

Security
--------

*Tip: How does this change impact security? Answer the following
questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**

toml

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

N/A. But we do read from a confiuration file thats either at a default location or specified by the user

**How do you validate new .samrc configuration?**



What is your Testing Plan (QA)?
===============================

Goal
----

App level Configuration files are tested alongside SAM CLI and are expected to work seamlessly with meaningful error messages to steer users towards using app level configuration files to manage their app workflows.

Pre-requesites
--------------

N/A

Test Scenarios/Cases
--------------------

* Integration tests for every command with app level configuration file overrides, and command line overrides on existing app level configuration files.
* Tested to work on all platforms

Expected Results
----------------
* Works on all platforms
* Resolution of parameters follows.
 * CLI parameters -> Config file parameters

Documentation Changes
=====================

* Addition of a new `--config` file parameter per command

Related Open Issues
============
* https://github.com/awslabs/aws-sam-cli/issues/975
* https://github.com/awslabs/aws-sam-cli/issues/748

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
