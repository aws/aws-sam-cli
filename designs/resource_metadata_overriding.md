Understand Resource Level Metadata
==================================

This is a design to capture how SAM CLI can support templates that are generated 
from different frameworks, e.g. AWS Cloud Development Kit.

Initially, the support will only be for processing Resource Metadata within the template, which enables support for
customers using AWS Cloud Development Kit (CDK).

What is the problem?
--------------------

Customers have different ways to define their AWS Resources. As of writing (Jan. 2019),
SAM CLI supports the use case of defining an application in CloudFormation/SAM (a super
set of CloudFormation). These CloudFormation/SAM applications are written in `json` or `yaml`
and deployed through AWS CloudFormation. Frameworks like CDK offer customers an alternative
in how they define their applications. SAM CLI should support the ability to invoke functions 
defined through these other frameworks to enable them to locally debug or manage their 
applications.

What will be changed?
---------------------

To start, we will add support for processing Resource Metadata that is embedded into the template:
SAM CLI will add a processing step on the templates it reads. This will consist of reading
the template and for each resource reading the Metadata and replacing values as specified.

In the future, we can support creating these templates from the different frameworks in a command directly within 
SAM CLI but is out of scope in the initial implementation of support.

Success criteria for the change
-------------------------------

* Ability to invoke functions locally that contain Metadata on a Resource
* Process a template with CDK Metadata on a resource.

Out-of-Scope
------------

* A command that will generate the template from the framework.

User Experience Walkthrough
---------------------------

CDK is a framework that appends this Metadata to Resources within a template and will use this as an example.

### Customer using CDK

A customer will use CDK to generate the template. This can be done by generating a template and saving it to a file:
`cdk synth > template.yaml`. Then will then be able to `sam local [invoke|start-api|start-lambda]` any 
function they have defined [1].   


[1] Note: The cdk version must be greater than v0.21.0 as the metadata needed to parse is not appended on older versions. 


Implementation
==============

CLI Changes
-----------

For the features currently in scope, there are no changes to the CLI interface.

### Breaking Change

No breaking changes

Design
------

All the providers, which are used to get resources out of the template provided to the command, call 
`SamBaseProvider.get_template(template_dict, parameter_overrides)` to get a normalized template. This function call is 
responsible for taking a SAM template dictionary and returning a cleaned copy of the template where SAM plugins have 
been run and parameter values have been substituted. Given the current scope of this call, expanding it to also normalize 
metadata, seems reasonable. We will expand `SamBaseProvider.get_tempalte()` to call a `ResourceMetadataNormalizer` class
that will be responsible for understanding the metadata and normalizing the template with respect to the metadata. 

Template snippet that contains the metadata SAM CLI will parse and understand.

```yaml

Resources:
    MyFunction:
      Type: AWS::Lambda::Function
      Properties:
        Code: 
          S3Bucket: mybucket
          S3Key: myKey
        ...
      Metadata:
        aws:asset:path: '/path/to/function/code'
        aws:asset:property: 'Code'
```

The two keys we will recognize are `aws:asset:path` and `aws:asset:property`. `aws:asset:path`'s value will be the path
to the code, files, etc that are on the machine, while `aws:asset:property` is the Property of the Resource that
needs to be replaced. So in the example above, the `Code` Property will be replaced with `/path/to/function/code`.

Below algorithm to do this Metadata Normalization on the template.

```python
class ResourceMetadataNormalizer(object):

    @staticmethod
    def normalize(template_dict):
        for resource in template_dict.get('Resources'):
            if 'Metadata' in resource:
                asset_property = resource.get('Metadata').get('aws:asset:property')
                asset_path = resource.get('Metadata').get('aws:asset:path')
                ResourceMetadataNormalizer.replace_property(asset_property, asset_path)
```

`.samrc` Changes
----------------

N/A

Security
--------

*Tip: How does this change impact security? Answer the following
questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**

None

**What other Docker container images are you using?**

None

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

* Blog or Documentation that explains how you can define an application in CDK and use SAM CLI to test/invoke

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
