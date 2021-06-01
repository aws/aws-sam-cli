SAM Config
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

* `sam deploy --template-file ... --stack-name ... --capabilities ... --tags ... --parameter-overrides ... --kms-key-id ...`

If this could be condensed into a series of workflows that look like

* `sam build`
* `sam package`
* `sam deploy`

That would be a huge user experience win.

Tenets
-------------------------------

* Resolution of command line parameters should always favor explicit versus implicit. A native command line parameter specified directly on the command line should override a parameter specified in the configuration file.

What will be changed?
---------------------

The suite of commands supported by SAM CLI would be aided by looking for a configuration file thats locally located under at the project root where template.yaml is located by default.

`samconfig.toml`


This configuration would be used for specifiying the parameters that each of SAM CLI commands use and would be in TOML format.

Running a SAM CLI command now automatically looks for `samconfig.toml` file and if its finds it goes ahead with parameter passthroughs to the CLI.

```
sam build
Default Config file location: samconfig.toml
..
..
..
```

Why `samconfig.toml` not under `.aws-sam` directory?
---------------------------------

The `.aws-sam` directory generally holds artifacts that are driven by the implementation details behind the sam cli commands themselves. A configuration file which controls how a sam app behaves should exist by itself as a first class citizen right next to the sam template.


Config file versioning
-----------------------

The configuration file: `samconfig.toml` will come with a top level version key that specifies the version of the configuration file based on the spec of the file. This version can then be used to determine if a given configuration file works with a given version of SAM CLI.

It also paves the forward when major changes need to be made to the configuration file and add a version bump to the config file version

```
version = 0.1
```

* SAM CLI expects the version format to follow a semantic format.
* SAM CLI will remain backward compatible with reading older configuration file versions.

Overrides
----------

The default location of a samconfig.toml can be replaced by overriding an environment variable called `SAM_CLI_CONFIG`

`
export SAM_CLI_CONFIG=~/Users/username/mysamconfig.toml
`

Users can choose to pass their own configuration file with a `--config-file` command line option.

Users can pass an environment `--config-env` for the section that will be scanned within the configuration file to pass parameters through.

By default the `default` section of the configuration is chosen.

```
version = 0.1

[default]

[default.build]
[default.build.parameters]
profile="srirammv"
debug=true
skip_pull_image=true
use_container=true

[default.package]
[default.package.parameters]
profile="srirammv"
region="us-east-1"
s3_bucket="sam-bucket"
output_template_file="packaged.yaml"

[default.deploy]
[default.deploy.parameters]
stack_name="using_config_file"
capabilities="CAPABILITY_IAM"
region="us-east-1"
profile="srirammv"

```

If a custom environment is specified, the environment is looked up in `samconfig.toml` file instead.

`sam build --config-env dev`

Sample configuration file

```
version = 0.1

[default.build.paramaters]
profile="srirammv"
debug=true
skip_pull_image=true
use_container=true

[default.package.parameters]
profile="srirammv"
region="us-east-1"
s3_bucket="sam-bucket"
output_template_file="packaged.yaml"

[default.deploy.parameters]
stack_name="using_config_file"
capabilities="CAPABILITY_IAM"
region="us-east-1"
profile="srirammv"


[dev.build.paramaters]
profile="srirammv"
debug=true
skip_pull_image=true
use_container=true

[dev.package.parameters]
profile="srirammv"
region="us-east-1"
s3_bucket="sam-bucket"
output_template_file="packaged.yaml"

[dev.deploy.parameters]
stack_name="using_config_file"
capabilities="CAPABILITY_IAM"
region="us-east-1"
profile="srirammv"
```

NOTE: Due to the nature of tomlkit or the interaction mode when writing configuration values to the configuration, there are multiple empty sections such as `[default.package]`. They need to be investigated.

Showcase configuration values
-----------------------------

On running SAM CLI commands with `--debug`, SAM CLI can output the values read from the configuration file. This way the user is always informed of the total set of parameters are being used by SAM CLI, when the customers need to debug what parameters are actually being passed to the `sam` commands.


Config file in Git Repos
------------------------

`samconfig.toml` file can be checked into a git repo, so that its ready to use on cloning the repo. if the configuration file does not present all the necesssary parameters, the command fails just as if one had specified the same arguments on the command line directly.

Optionally, if multiple configuration files are checked in. One can change the `SAM_CLI_CONFIG` environment variable to point a different configuration file.

`--config-env` can also be passed in to deal with custom environments defined in the configuration file.

Error Messages
---------------

When a custom config prefix is passed in, and such an environment is not found. The error message can highlight all the environments that were found in the given configuration file.

`
sam build --config-env devo
Error: Environment 'devo' was not found in samconfig.toml , Possible environments are : ['default', 'dev', 'prod']
`

Future
----------

If multiple default file locations are added in the look up order for `samconfig.toml`, this means that multiple config files can be merged together.

For example, if the hierachy of lookup for configuration files are: $SAM_CLI_CONFIG -> `samconfig.toml` -> `~/.aws-sam/samconfig.toml`

The resulting configuration would be a merge of all the sections that are relevant for the command that was run.

This way, configuration that might be global can be placed in `~/.aws-sam/samconfig.toml`.

```
version = 0.1
[default.build.parameters]
use_container = True
skip_pull_image = True
```

Project specific configuration placed in `~/.aws-sam/samconfig.toml`

```
version = 0.1
[default.build.parameters]
parameter_overrides="ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"
```

Eventual merged configuration read during `sam build` in-memory.

```
version = 0.1
[default.build.parameters]
use_container = True
skip_pull_image = True
parameter_overrides="ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro"
```

* How different versions of the configuration files will be merge-able is still an open question.
* Can `--config-file` take multiple parameters as arguments and thereby merge all of them together?

Open Questions
-------------------------------

* Potentially every sam command could have functionality to have a series of command line parameters exported into a configuraion file.


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

Implemented
-----------
* Default configuration file for sam cli commands for parameter passthroughs.

Not Implemented
---------------
* New command line argument for specifying configuration file via `--config-file`.
* New command line argument per command called `--config-env` to be able to specify non default environment section within a config file.

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

A custom callback function (`configuration_callback`) (for the click option) that takes in a custom configuration parser (`provider`) will have rules in place, on how the corresponding configuration can be retrieved and what are the parts that the configuration parser has access to read from.

```
provider = attrs.pop("provider", TomlProvider(rules=DefaultRules(), command="build", section="parameters"))
attrs["type"] = click.STRING
saved_callback = attrs.pop("callback", None)
partial_callback = functools.partial(onfiguration_callback, cmd_name, option_name, env_name, saved_callback, provider)
attrs["callback"] = partial_callback
click.option(*param_decls, **attrs)(f)

```

Phases
------

The design can be built in phases.

* No option to specify configuration file or configuration prefix ✅
* Specify configuration file with an environment variable and with a command line argument `--config-file`
* Read `--config-env` to make sure we can select an appropriate portion in configuration file.


Security
--------

*Tip: How does this change impact security? Answer the following
questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**

tomlkit

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

N/A. But we do read from a confiuration file thats either at a default location or specified by the user via an environment variable.


What is your Testing Plan (QA)?
===============================

Goal
----

Configuration files are tested alongside SAM CLI and are expected to work seamlessly with meaningful error messages to steer users towards using configuration file to manage their app workflows.

Pre-requesites
--------------

N/A

Test Scenarios/Cases
--------------------

* Integration tests for every command with `--config-file` and `--config-env` based overrides, and command line overrides on existing sam configuration file and custom configuration file through environment variables.
* Tested to work on all platforms

Expected Results
----------------
* Works on all platforms
* Resolution of parameters follows.
 * CLI parameters -> Config file parameters

Documentation Changes
=====================

* Addition of a new `--config-file` parameter per command
* Addition of a new `--config-env` parameter per command

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
