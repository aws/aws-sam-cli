What is the problem?
--------------------
* sam build does not support building for `provided` runtimes.
* sam build also does not allow customization of the build process for the supported lambda runtimes.

What will be changed?
---------------------

Serverless Function resources can now have a Metadata Resource Attribute which specifies a `BuildMethod`. 
`BuildMethod` will either be the official lambda runtime identifiers such as `python3.8`, `nodejs12.x` etc or `makefile`.
If `BuildMethod` is specified to be `makefile`, the build targets that are present in the `Makefile` which take the form of

`build-{resource_logical_id}` will be executed.

More details can also be found at: [CustomMakeBuildWorkflow](https://github.com/awslabs/aws-lambda-builders/blob/develop/aws_lambda_builders/workflows/custom_make/DESIGN.md)

This enables following usecases:

* build for `provided` runtimes.
* user specified build steps for official lambda supported runtimes instead of what `sam build` natively offers.

Success criteria for the change
-------------------------------

* Users are able to build for `provided` runtimes through sam build directly.
* Users are able to bring their own build steps for even natively supported lambda runtimes.

User Experience Walkthrough
---------------------------

#### Provided runtimes

Template

```yaml
Resources:
  HelloRustFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: bootstrap.is.real.handler
      Runtime: provided
      MemorySize: 512
      CodeUri: .
    Metadata:
      BuildMethod: makefile
```

Makefile

```
build-HelloRustFunction:
	cargo build --release --target x86_64-unknown-linux-musl
	cp ./target/x86_64-unknown-linux-musl/release/bootstrap $(ARTIFACTS_DIR)
```

#### Makefile builder for lambda runtimes

Template

```yaml
Resources:
  HelloWorldFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: hello_world/
      Handler: app.lambda_handler
      Runtime: python3.7
    Metadata:
      BuildMethod: makefile
```

Makefile

```
build-HelloWorldFunction:
    cp *.py $(ARTIFACTS_DIR)
    cp requirements.txt $(ARTIFACTS_DIR)
    python -m pip install -r requirements.txt -t $(ARTIFACTS_DIR)
    rm -rf $(ARTIFACTS_DIR)/bin
```

Implementation
==============
### Proposal

* Selection of the build workflow within sam cli will now have additional logic to select the correct build workflow from user input in the template.
Currently, a build workflow is chosen based on the lambda runtime and the manifest file alone.

FAQs
----
1. Can a user specify the BuildMethod to be `python3.8` for a `python3.8` runtime?
    * Yes, this will just select the native python workflow that is used from `aws-lambda-builders` 
2. Can a user specify BuildMethod to be `ruby2.7` for a `python3.8` runtime?
    * Theoretically yes, But the build will just fail.
3. Can a user specify the BuildMethod to be `python3.7` for a `python3.8` runtime?
    * Theoretically yes, However If the user is just using the builder that samcli already provides, 
    its best not to provide any `BuildMethod` at all.


CLI Changes
-----------

No changes in CLI interface.

### Breaking Change

No breaking changes.


What is your Testing Plan (QA)?
===============================

* Unit and Integration testing

Goal
----

* Coverage of usecases such as:
    * build for `provided` runtimes
    * build for official lambda runtimes through the `makefile` construct
    * build within containers for the `makefile` construct


Expected Results
----------------
* Integration tests to pass that covers usecases listed in the goal.


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
