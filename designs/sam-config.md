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

The suite of commands supported by SAM CLI would be aided by looking for a configuration file thats locally located under the `.aws-sam/` at the project root where template.yaml is located by default.

`.aws-sam/samconfig.toml`


This configuration would be used for specifiying the parameters that each of SAM CLI commands use and would be in TOML format.

Running a SAM CLI command now automatically looks for `.aws-sam/samconfig.toml` file and if its finds it goes ahead with parameter passthroughs to the CLI.

```
sam build
Default Config file location: .aws-sam/samconfig.toml
..
..
..
```

Why samconfig under `.aws-sam`
---------------------------------

> The below two don't answer the above question. Instead, they give technical implementation answers to questions not asked like "How is the .aws-sam directory made?" and "Are any files in .aws-sam git ignored?". The ideas surfaced in the previous PR's discussion were lost. For example, in the PR threads it was for a short time in the root of the project but then put back into .aws-sam. I recommend clearly stating here an answer to the above question in terms of goals, not technical implementations.

The `.aws-sam` directory within the project directory is created with normal 755 permissions as default without any special permisions. `sam build` only creates a build directory within `.aws-sam` as `.aws-sam/build`. This directory is erased and re-built on every build. but top level directory is left unaffected.

The `.gitignore` specified in the init apps also only have `.aws-sam/build` ignored and not anything else.


Config file versioning
-----------------------

The configuration file: `samconfig.toml` will come with a top level version key that specifies the grammar version of the configuration file. This version can then be used to determine if a given configuration file works with a version of SAM CLI. A given version of SAM CLI may support one or more configuration file grammar versions.

> The above clarifies that the version is not the version of the file itself (like an ever increasing commit version), instead it is the version of the grammar/DTD/spec of the file.

It also paves the forward when major changes need to be made to the configuration file and add a version bump to the config file version

```
version = 0.1
```

> What is behavior of SAM CLI for different scenarios, e.g.:
> 1. SAM CLI given file with version number that this SAM CLI doesn't support
> 2. SAM CLI parses file but discovers that file doesn't comply with spec of that version
> 3. SAM CLI tries to merge multiple configuration files together of differing spec versions

Overrides
----------

The default location of a .aws-sam/samconfig can be replaced by overriding an environment variable called `SAM_CLI_CONFIG`

`
export SAM_CLI_CONFIG=~/Users/username/mysamconfig.toml
`

Users can pass an environment `--env` for the section that will be scanned within the configuration file to pass parameters through.

> I hesitate in using `--env` as the param that controls what prefix of TOML tables/sections is parsed/loaded. Using `--env` strongly associates a specific usage scenario (environment choice) to a feature that is much broader in potential usage. Also, `--env` doesn't to me clarify what it controls/changes. At first read, I think it controls environment variables. Perhaps an alternative like `--config-prefix` which is no longer limited to a specific usage scenario while more clearly describing what it controls.

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

> I am not in favor of having empty TOML tables/sections like `[default.package]`.
> Also not in favor of trailing ...`.parameters]`. Neither are adding value and instead extra boilerplate/bytes.

If a custom environment is specified, the environment is looked up in `samconfig.toml` file instead.

`sam build --env dev`

Sample configuration file

```
version = 0.1

[default.build.parameters]
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


[dev.build.parameters]
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


The configuration file can then be potentially intialized

* all sam init projects could come with a sample samconfig file

Showcase configuration values
-----------------------------

On running SAM CLI commands with `--debug`, SAM CLI can output the values read from the configuration file. This way the user is always informed of the total set of parameters are being used by SAM CLI, when the customers need to debug what parameters are actually being passed to the `sam` commands.


Config file in Git Repos
------------------------

`samconfig.toml` file can be checked into a git repo, so that its ready to use on cloning the repo. if the configuration file does not present all the necesssary parameters, the command fails just as if one had specified the same arguments on the command line directly.

Optionally, if multiple configuration files are checked in. One can change the `SAM_CLI_CONFIG` environment variable to point a different configuration file.

`--env` can also be passed in to deal with custom environments defined in the configuration file.

Error Messages
---------------

When a custom env is passed in, and such an environment is not found. The error message can highlight all the environments that were found in the given configuration file.

`
sam build --env devo
Error: Environment 'devo' was not found in .aws-sam/samconfig.toml , Possible environments are : ['dev', 'prod']
`

> I'm not in favor the 2nd part of the above error message; not in favor of reporting what TOML table/section prefixes (aka environments) are in the config file. That behavior that is very odd and unfamiliar to me. It also adds additional code + test cases for a feature I don't see value in. The first part of that error message is great. Just tell me that the prefix I specified was not found. Done.

Future
----------

In the future, based on the file names of the configuration files, the environment could also be inferred.

```
.aws-sam/samconfig-dev.toml
.aws-sam/samconfig-beta.toml
.aws-sam/samconfig-prod.toml
```

`--env` dev will refer to `.aws-sam/samconfig-dev.toml` and so on.

> I'm not in favor of parsing file names in lieu of TOML table/section prefixes. What are the TOML tables in the first file? Does it contain `[dev.build.parameters]` or just `[build.parameters]` or `[default.build.parameters]`. First is redundant, second is out-of-spec, third is potentially confusing since there could be defaults elsewhere.
> Instead, I support loading of multiple config files in order they are specified. Similar to how `docker-compose` can have multiple `-f filename` parameters. However, then comes the discussion of merge rules: overwrite/append keys, extend arrays, and application of these merge rules across files across defaults, merge rules for config files of different spec versions, etc.?

If multiple default file locations are added in the look up order for `samconfig.toml`, this means that multiple config files can be merged together.

For example, if the hierachy of lookup for configuration files are: $SAM_CLI_CONFIG -> `.aws-sam/samconfig.toml` -> `~/.aws-sam/samconfig.toml`

The resulting configuration would be a merge of all the sections that are relevant for the command that was run.

This way, configuration that might be global can be placed in `~/.aws-sam/samconfig.toml`.

```
version = 0.1
[default.build.parameters]
use_container = True
skip_pull_image = True
```

Project specific configuration placed in `.aws-sam/samconfig.toml`

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

Open Questions
-------------------------------

* Potentially every sam command could have functionality to have a series of command line parameters exported into a configuraion file.


Out-of-Scope
------------

* Not focusing on a global configuration. SAM CLI already has a notion of a global config at `~/.aws-sam/metadata.json`

> This is confusing/conflicting with a few paragraphs above is written, "This way, configuration that might be global can be placed...". While technically such could be possible, I recommend not writing of a technically possible scenario that conflicts with what is stated as out-of-scope.

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

New command line argument is added per command called `--env` to be able to specify non default environment section within a config file.


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

* No option to specify configuration file or env name
* Specify configuration file with an environment variable
* Read `--env` to make sure we can select an appropriate portion in configuration file.


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

N/A. But we do read from a confiuration file thats either at a default location or specified by the user via an environment variable.

**How do you validate new .samrc configuration?**



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

* Integration tests for every command with `env` based overrides, and command line overrides on existing sam configuration file and custom configuration file through environment variables.
* Tested to work on all platforms

Expected Results
----------------
* Works on all platforms
* Resolution of parameters follows.
 * CLI parameters -> Config file parameters

Documentation Changes
=====================

* Addition of a new `--env` parameter per command

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
