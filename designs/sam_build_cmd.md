`sam build` command
===================

This is the design for a command to **build** a Lambda function.
**Build** is the operation of converting the function\'s source code to
an artifact that can be executed on AWS Lambda.

What is the problem?
--------------------

To run a function on AWS Lambda, customers need to provide a zip file
containing an executable form of the code. The process of creating the
executable usually involves downloading dependent libraries, optionally
compiling the code on Amazon Linux, copying static assets, and arranging
the files in a directory structure that AWS Lambda accepts. In some
programming languages like Javascript, this process is fairly
straightforward (just zip a folder), and in others like Python, it is
much involved.

Customers using SAM CLI can easily create Lambda function code (using
`sam init`) and package their artifact as a zip file (using
`sam package`), but they have to handle the build process themselves.
Customers usually implement their own build scripts or adopt other\'s
scripts from the internet. This is where many customers fall off the
cliff.

What will be changed?
---------------------

In this proposal, we will be providing a new command, `sam build`, to
build Lambda functions for all programming languages that AWS Lambda
supports. The cardinality of the problem is number of programming
languages (N) times the number of package managers (M) per language.
Hence is it is nearly impossible to natively support each combination.
Instead, `sam build` will support an opinionated set of package managers
for all programming languages. In the future, we will provide an option
for customers to bring their own build commands or override the default
for any programming language. SAM CLI will still take care of the grunt
work of iterating through every function in the SAM template, figuring
out the source code location, creating temporary folders to store built
artifacts, running the build command and move artifacts to right
location.

Success criteria for the change
-------------------------------

1.  Support all programming languages supported by AWS Lambda
    -   Nodejs with NPM
    -   Java with Maven
    -   Python with PIP
    -   Golang with Go CLI
    -   Dotnetcore with DotNet CLI
2.  Each Lambda function in SAM template gets built by default unless a `function_identifier` (LogicalID) is passed 
    to the build command
3.  Produce stable builds (best effort): If the source files did not
    change, built artifacts should not change.
4.  Built artifacts should \"just work\" with `sam local` and
    `sam package` suite of commands
5.  Opt-in to building native dependencies that can run on AWS Lambda
    using Docker.
6.  Support one dependency manifest (ex: package.json) per each Lambda
    function.
7.  Support out-of-source builds: ie. source code of Lambda function is
    outside the directory containing SAM template.
8.  Integrate build action with `sam local/package/deploy` commands so
    the Lambda functions will be automatically built as part of the
    command without explicitly running the build command.
9.  Support for building the app for debugging locally with debug
    symbols (ex: Golang) [see design doc](build_debug_artifacts.md)

Out-of-Scope
------------

1.  Ability to provide arbitrary build commands for each Lambda Function
    runtime. This will either override the built-in default or add build
    support for languages/tools that SAM CLI does not support (ex:
    java+gradle).
2.  Supports adding data files ie. files that are not referenced by the
    package manager (ex: images, css etc)
3.  Support to exclude certain files from the built artifact (ex: using
    .gitignore or using regex)
5.  Support caching dependencies & re-installing them only when the
    dependency manifest changes (ex: by maintaining hash of
    package.json)
6.  If the app contains a `buildspec.yaml`, automatically run it using
    CodeBuild Local.
7.  Watch for file changes and build automatically (ex:
    `sam build --watch`)
8.  Support other build systems by default Webpack, Yarn or Gradle.
9.  Support in AWS CLI, `aws cloudformation`, suite of commands
10. Support for fine-grained hooks (ex: hooks that run pre-build,
    post-build, etc)
11. Support one dependency manifest per app, shared by all the Lambda
    functions (this is usually against best practices)

User Experience Walkthrough
---------------------------

Let\'s assume customers has the following SAM template:

> **NOTE**: Currently we advice customers to set *CodeUri* to a folder
> containing built artifacts that can be readily packaged by
> `sam package` command. But to use with *build* command, customers need
> to set *CodeUri* to the folder containing source code and not built
> artifacts.

``` {.sourceCode .yaml}
MyFunction1:
    Type: AWS::Lambda::Function
    Properties:
        ...
        Code: ./source-code1
        ...

MyFunction2:
    Type: AWS::Serverless::Function
    Properties:
        ...
        Code: ./source-code2
        ...
```

To build, package and deploy this app, customers would do the following:

**1. Build:** Run the following command to build all functions in the
template and output a SAM template that can be run through the package
command:

``` {.sourceCode .bash}
# Build the code and write artifacts to ./build folder
# NOTE: All arguments will have sensible defaults so users can just use `sam build`
$ sam build -t template.yaml -b ./build -o built-template.yaml
```

Output of the *sam build* command is a SAM template where CodeUri is
pointing to the built artifacts. Note the values of Code properties in
following output:

``` {.sourceCode .bash}
$ cat built-template.yaml
MyFunction1:
    Type: AWS::Lambda::Function
    Properties:
        ...
        Code: ./build/MyFunction1
        ...

MyFunction2:
    Type: AWS::Serverless::Function
    Properties:
        ...
        CodeUri: ./build/MyFunction2
        ...
```

**2. Package and Deploy:** Package the built artifacts by running the
*package* command on the template output by *build* command

``` {.sourceCode .bash}
# Package the code
$ sam package --template-file built-template.yaml --s3-bucket mybucket --output-template-file packaged-template.yaml

# Deploy the app
$ sam deploy --template-file packaged-template.yaml --stack-name mystack
```

### Other Usecases

1.  **Build Native Dependencies**: Pass the `--native` flag to the
    *build* command. This will run the build inside a Docker container.
2.  **Out-of-Source Builds**: In this scenario, Lambda function code is
    present in a folder outside the folder containing the SAM template.
    Absolute path to these folders are determined at runtime in a build
    machine. Set the `--root=/my/folder` flag to absolute path to the
    folder relative to which we will resolve relative *CodeUri* paths.
3.  **Inherited dependency manifest**: By default, we will look for a
    dependency manifest (ex: package.json) at same folder containing SAM
    template. If a `--root` flag is set, we will look for manifest at
    this folder. If neither locations have a manifest, we will look for
    a manifest within the folder containing function code. Manifest
    present within the code folder always overrides manifest at the
    root.
4.  **Arbitrary build commands**: Override build commands per-runtime by
    specifying full path to the command in `.samrc`.
5.  **Build & Run Locally**: Use the `--template` property of
    `sam local` suite of commands to specify the template produced by
    *build* command (ex: `build-template.yaml`)

Implementation
==============

CLI Changes
-----------

*Explain the changes to command line interface, including adding new
commands, modifying arguments etc*

1.  Adding a new top-level command called `sam build`.
2.  Add `built-template.yaml` to list of default template names searched
    by `sam local` commands

### Breaking Change

*Are there any breaking changes to CLI interface? Explain*

No Breaking Change to CLI interface

Design
------

*Explain how this feature will be implemented. Highlight the components
of your implementation, relationships* *between components, constraints,
etc.*

Build library provides the ability to execute build actions on each
registered resource. A build action is either a built-in functionality
or a custom build command provided by user. At a high level, the
algorithm looks like this:

``` {.sourceCode .python}
for resource in sam_template:
    # Find the appropriate builder
    builder = get_builder(resource.Type)

    # Do the build
    output_folder = make_build_folder(resource)
    builder.build(resource.Code, resource.runtime, output_folder)
```

We will keep the implementation of build agnostic of the resource type.
This opens up the future possibility of adding build actions to any
resource types, not just Lambda functions. Initially we will start by
supporting only the resource types `AWS::Serverless::Function` and
`AWS::Lambda::Function`.

### Build Folder

Default Location: `$PKG_ROOT/build/`

By default, we will create a folder called `build` right next to where
the SAM template is located. This will contain the built artifacts for
each resource. Customers can always override this folder location.

Built artifacts for each resource will be stored within a folder named
with the LogicalID of the resource. This allows us to build separate zip
files for each Lambda, so users can update one Lambda without triggering
an update on another. The same model will work for building other
non-Lambda resources.

*Advantages:*

-   Extensible to other resource types
-   Supports parallel builds for each resource
-   Aligned with a CloudFormation stack

*Disadvantages:*

-   Too many build folders, and hence zip files, to manage.
-   Difficult to share code between all Lambdas.

<!-- -->

    $PKG_ROOT/build/
        artifacts.json (not for MVP)
        MyFunction1/
             .... <build artifacts>

          MyFunction2/
             ... <build artifacts>

          MyApiGw/
            ... <build artifacts>

          MyECRContainer/
             ... <build artifacts>

#### Future Extensions

In the future, we will change the limitation around each folder being
named after the resource\'s LogicalID. Instead, we will support an
artifacts.json file that will map Lambda function resource's LogicalId
to the path to a folder that contains built artifacts for this function.
This allows us to support custom build systems that use different folder
layout.

A well-known folder structure also helps "sam local" and "sam package"
commands to automatically discover the built artifacts for each Lambda
function and package it.

### Stable Builds

A build is defined to be stable if the built artifacts changes if and
only if the contents or metadata (ex: timestamp, ownership) on source
files changes. This is an important attribute of a build system. Since
SAM CLI relies on 3rd party package managers like NPM to do the heavy
lifting, we can only provide a "best effort" service here. By running
`sam build` on a build system that creates a new environment from
scratch (ex: Travis/CircleCI/CodeBuild/Jenkins etc), you can achieve
truly stable builds. For more information on why this is important,
refer to Debian\'s guide on [reproducible
builds](https://reproducible-builds.org/).

SAM CLI does the following to produce stable builds:

1.  Clean build folder on every run
2.  Include metadata when coping files and folders
3.  Run build actions with minimal information passed from the
    environment

### Built-in Build Actions

Build actions natively supported by SAM CLI follow a standard workflow:

1.  Search for a supported dependency manifest file. If a known manifest
    is not present, we will abort the build.
2.  Setup: Create build folder
3.  Resolve: Install dependencies
4.  Compile: Optionally, compile the code if necessary
5.  Copy Source: Optionally, Copy Lambda function code to the build
    folder

Setup step is shared among all runtimes. Other steps in the workflow are
implemented differently for each runtime.

#### Javascript using NPM

Install dependencies specified by `package.json` and copy source files

**Manifest Name**: `package.json`

**Files Excluded From Copy Source**: `node_modules/*`

| Action      | Command                               |
| ----------- | ------------------------------------- |
| Resolve     | `npm install`                         |
| Compile     | No Op                                 |
| Copy Source | Copy files and exclude `node_modules` |

#### Java using Maven

Let Maven take care of everything

**Manifest Name**: `pom.xml`

**Files Excluded From Copy Source**: N/A


| Action        |  Command       |
|---------------|----------------|
| Resolve       |  No Op         |
| Compile       |  `mvn package` |
| Copy Source   |  No Op         |


#### Golang using Go CLI

Go\'s CLI will build the binary.

**Manifest Name**: `Gopkg.toml`

**Files Excluded From Copy Source**: N/A

| Action        |  Command                                         |
|---------------|--------------------------------------------------|
| Resolve       |  `dep ensure -v`                                 |
| Compile       |  `GOOS=linux go build  -ldflags="-s -w" main.go` |
| Copy Source   |  No Op                                           |


#### Dotnet using Dotnet CLI

**Manifest Name**: `*.csproj`

**Files Excluded From Copy Source**: N/A


| Action        |  Command                                                                             |
|---------------|--------------------------------------------------------------------------------------|
| Resolve       |  No Op                                                                               |
| Compile       |  `dotnet lambda package --configuration release --output-package $BUILD/package.zip` |
| Copy Source   |  No Op                                                                               |


#### Python using PIP

**Manifest Name**: `requirements.txt`

**Files Excluded From Copy Source**: `*.pyc, __pycache__`

| Action        |  Command                                                                             |
|---------------|--------------------------------------------------------------------------------------|
| Resolve       |  `pip install --isolated --disable-pip-version-check -r requirements.txt -t $BUILD`  |                                                       
| Compile       |  No Op                                                                               |
| Copy Source   |  Copy all files                                                                      |


### Implementation of Build Actions

Some of the built-in build actions are implemented in the programming
language that the actions supports. For example, the Nodejs build action
will be implemented in Javascript to take advantage of language-specific
libraries. These modules are called **builders**. This is a reasonable
implementation choice because customers building Nodejs apps are
expected to have Node installed on their system. For languages like
Golang, we will delegate entire functionality to `go` tool by invoking
it as a subprocess. The SAM CLI distribution will now bundle Javascript
code within a Python package, which even though seems odd, carries
value.

**Pros:**

-   Easy to lift & shift
-   Easy to use language specific libraries that can support deeper
    integrations in future like webpack build or running gulp scripts
-   Sets precedence for other runtimes like Java which might need
    reflexion to create the package
-   Easier to get help from JS community who is more familiar with
    building JS packages.

**Cons:**

-   Vending JS files in Python package
-   Might take dependency on certain version of Node. We can\'t enforce
    that customers have this version of Node on their system.
-   Might have to webpack all dependencies, minify and vend one file
    that we just run using node pack.js.
-   Could become a tech debt if this approach doesn\'t scale.

#### Builder Interface

In this implementation model, some steps in the build action are
implemented natively in Python and some in a separate programming
language. To complete a build operation, SAM CLI reads SAM template,
prepares necessary folder structure, and invokes the appropriate builder
process/command by passing necessary information through stdin as
JSON-RPC. SAM CLI waits for a JSON-RPC response back through stdout of
the process and depending on the status, either fails the build or
proceeds to next step.

**Input:**

``` {.sourceCode .json}
{
    "jsonrpc": "2.0",

    "id": "42",

    // Only supported method is `resolve-dependencies`
    "method": "resolve-dependencies",
    "params": {
        "source_dir": "/folder/where/source/files/located",
        "build_dir": "/directory/for/builder/artifacts",
        "runtime": "aws lambda function runtime ex. node8.10",
        "template_path": "/path/to/sam/template"
    }
}
```

**Output:**

``` {.sourceCode .json}
{
    "jsonrpc": "2.0",

    "id": "42",

    "result": {
        // No result expected for successful execution
    }
}
```

### Building Native Binaries

To build native binaries, we need to run on an architecture and
operating system that is similar to AWS Lambda. We use the Docker
containers provided by [Docker
Lambda](https://github.com/lambci/docker-lambda) project to run the same
set of commands described above on this container. We will mount source
code folder and build folder into the container so the commands have
access to necessary files.

`.samrc` Changes (Out-of-Scope)
-------------------------------

*Explain the new configuration entries, if any, you want to add to
.samrc*

We will add a new section to `.samrc` where customers can provide custom
build actions. This section will look like:

``` {.sourceCode .json}
{
    "build": {
        "actions": {
            "java8": "gradle build",
            "dotnetcore2.1": "./build.sh"
        }
    }
}
```

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

**How do you validate new .samrc configuration?**

Documentation Changes
---------------------

TBD

Open Questions
--------------

1.  Should we support `artifacts.json` now to be future-proof? **Answer:
    NO**
2.  Should we create the default `build` folder within a `.sam` folder
    inside the project to provide a home for other scratch files if
    necessary? **Answer: Out of Scope for current implementation**

Task Breakdown
--------------

-   \[x\] Send a Pull Request with this design document
-   \[ \] Build the command line interface
-   \[ \] Wire up SAM provider to discover function to build
-   \[ \] Library to build Python functions for MVP (others languages
    will follow next)
-   \[ \] Add `built-template.yaml` to list of default template names
    searched by `sam local` commands
-   \[ \] Update `sam init` templates to include `sam build` in the
    README
-   \[ \] Unit tests
-   \[ \] Functional Tests
-   \[ \] Integration tests
-   \[ \] Run all tests on Windows
-   \[ \] Update documentation
