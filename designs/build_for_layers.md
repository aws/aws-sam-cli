What is the problem?
--------------------
AWS Lambda Layer is a ZIP archive that contains libraries, a custom runtime, or other dependencies. Layers allow us to keep our deployment package small, which makes development easier. To include libraries in a layer, they need to be placed in pre decided folders. For more information check [here](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html#configuration-layers-path). Once files are in proper folder structure it can be zipped and uploaded to S3 where it’ll be ready to be used by Lambda Function.

Current layer support of aws-sam-cli expects layer folder to be in final condition which then is zipped and uploaded to S3. That means if one need to compile java code, they have to do that outside of their sam-cli workflow. This design is solving this problem by including layer building process in sam build which will reduce the overhead to build layer separately outside of sam workflow.

Out-of-Scope
------------
1. Implementation of Makefile based build. That is already in progress under [PR-166](https://github.com/awslabs/aws-lambda-builders/pull/166)

User Experience Walkthrough
---------------------------
1. Add Metadata (check proposal for more details) to the layers in template.yaml file to opt-in to build for layers.
1. Provide ManifestPath if applicable.
1. Run `sam build` to build all functions and layers.
1. Run `sam build FunctionLogicalID` to build single Function and all layers this function depend on.
1. Run `sam build LayerLogicalID` to build single layer.

Implementation
==============
### Proposal
Build for layers will build Layer from aws-sam-cli and prepare artifacts in expected folder structure. Check [this](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html#configuration-layers-path) for more details around expected folder structure.
Build for layers will choose one of the following types of build workflows:
#### NoBuildWorkflow
This is not exactly a workflow. However, if user do not want to build their Layer using build for layers, then they don’t have to do anything. This feature is opt-in and if no `Metadata -> BuildMethod` is provided then we’ll keep following current workflow.

#### StandardBuildWorkflow
Sample YAML:
```
MyLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      ContentUri: my_layer
      CompatibleRuntimes:
        - python3.8
    Metadata:
      BuildMethod: python3.8 (or nodejs8.10 etc..)
```
StandardBuildWorkflow do not expect any manifest file, and have simple 1:1 mapping with AWS Serverless Function runtime. This BuildMethod helps us choose correct build workflow for layer from `aws-lambda-builders`. If this workflow is chosen, aws-sam-cli will be responsible for putting build artifact in layer specific folder structure.

#### MakefileBuildWorkflow
Sample YAML:
```
MyLayer:
    Type: AWS::Serverless::LayerVersion
    Properties:
      ContentUri: my_layer
      CompatibleRuntimes:
        - python3.8
    Metadata:
      BuildMethod: makefile
```
This workflow will check for a Makefile with build target `build-{LayerLogicalID}`. For more details around this workflow check [PR-166](https://github.com/awslabs/aws-lambda-builders/pull/166). User can use `--manifest` option of `sam build` command to override path to manifest file. If no path is provided, sam-cli will look for makefile in ContentUri of layer. If this workflow is chosen, user will be responsible for generating build artifacts in layer specific folder structure.

#### Alternatives Considered
* Instead of making Metadata field mandatory we can also try to detect build workflow based on compatible runtime provided. The problem with this approach is that it somewhat breaks backwards compatibility. Eg: If somebody have a python layer, but is already using Makefile to custom build it then us running python build workflow will not work. Even if we detect makefile we don’t know the actions needed to build the layer.
* Instead of using Metadata in template.yaml file, we can make entries in samconfig.toml file. We can use samconfig.toml file, however, that file is intended to configure sam-cli. If we decide to support only one build type at a time (eg: one can only use python workflow to build all layers) then it might work. However, for all other cases we have to mention LogicalID of layer in samconfig toml file, which is not the intended purpose of samconfig.

FAQs
----
**What if user want to use separate Makefile for Lambda and Layer but still want to pass `--manifest` option.**   
This edge case is currently not supported. Implementation of this require addition in sam-cli interface and would be a much bigger change. We will implement this feature if lot of users will ask for this.

CLI Changes
-----------

No changes in CLI interface.

### Breaking Change

No breaking changes.

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
