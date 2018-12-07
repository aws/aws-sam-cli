.. contents:: **Table of Contents**
   :depth: 2
   :local:

``sam build`` support for Layers
================================
This is the design for add the capability to **build** a Lambda Layer. **Build** is the operation of converting the function's
source code to an artifact that can be executed on AWS Lambda.


What is the problem?
--------------------
``sam build`` was implemented with only the ability to build Lambda Functions. At re:Invent 2018, Lambda launched a new
resource called Layer. This allows customers make code/files available during the invoke of a function without
those files/code being packaged up directly with the function code itself. Just like with Functions, customers
will need to build these layers for the Lambda Environment.


What will be changed?
---------------------
``sam build`` will need to be able to parse and understand the Layer Resource (both SAM and vanilla CloudFormation) and
then produce an artifact in the ``.aws-sam/build`` folder that can be packaged to allow execution on AWS Lambda.


Success criteria for the change
-------------------------------
* Layers that define one runtime, will produce an artifact in ``.aws-sam/build``
* The built template will point to the built artifact, if that resource was built
* As more runtimes get added to ``sam build``, there will be no action to support layers for those runtimes


Out-of-Scope
------------
* Building for multiple runtimes
    * Building for many runtimes is a complex operation. You can't build for the highest version and guarantee it will
      work for all runtimes specified. For example, in Python you can define different requirements to be used based
      on the Python version being used. This means the artifacts generated from using Python 3.6 and Python 2.7 may not
      be the same. Which would result in layer breaking at runtime for missing dependencies depending on the Lambda
      Runtime.
* Building for runtimes that ``sam build`` command currently does not support
* Building Layers that define no compatible runtimes


User Experience Walkthrough
---------------------------
Experience is the same as the initially design of `build <sam_build_cmd.rst>`__ with that addition of supporting
that workflow with templates that have Layer Resources.

A Layer Resource's Content location (local directory) must have a manifest file. This is the same restrictions Functions
have and we will keep these consistent across Layers and Functions.

Implementation
==============

CLI Changes
-----------
*Explain the changes to command line interface, including adding new commands, modifying arguments etc*

No changes to the CLI's interface needed to support building Layers.

Breaking Change
~~~~~~~~~~~~~~~
*Are there any breaking changes to CLI interface? Explain*

No

Design
------
*Explain how this feature will be implemented. Highlight the components of your implementation, relationships*
*between components, constraints, etc.*

The BuildContext currently has a property for a function_provider. As we expand to building more resources, we need
the framework to support this seamlessly.

```
class BuildContext(object):

    ...

    @property
    def function_provider(self):
        return self._function_provider

    ...
```

We will update this the ``function_provider`` property to be a ``resource_provider`` that will return the list of
providers that will be used to get different types of resources from the template.


```
class BuildContext(object):

    ...

    @property
    def resource_providers(self):
        return [self._function_provider, self._layer_provider]

    ...
```

With this, we need to expand the ApplicationBuilder class as well. Since we are building different resources. The class
will be updated to:

```
class ApplicationBuilder(object):

    def __init__(self,
                 provider_list,
                 build_dir,
                 base_dir,
                 manifest_path_override=None,
                 container_manager=None,
                 parallel=False):
        pass

    def build(self):
        """
        Build the entire application.

        For each provider in provider_list:
            For each resource in the provider:
                build

        Returns
        -------
        dict
            Returns the path to where each resource was built as a map of resource's LogicalId to the path string
        """
        pass
```

The ApplicationBuilder no longer understands a single provider. This requires the building logic to live at each
resource.

For each data model that represents a resource will implement a build method. This will allow each resource to define
whether or not is can be built by ``sam build``.

Taking Functions as an example. The ``_build_function`` method in ApplicationBuilder will be moved to the Function
model directly.

Will will create a new class to encapsulate the ``_build_function_in_process`` and ``_build_function_on_container``,
which are specific to the service the resource is being built for.


```
class LambdaBuilder(object):

    def _build_function_in_process(self,
                                   config,
                                   source_dir,
                                   artifacts_dir,
                                   scratch_dir,
                                   manifest_path,
                                   runtime):
        pass

    def _build_function_on_container(self,  # pylint: disable=too-many-locals
                                     config,
                                     source_dir,
                                     artifacts_dir,
                                     scratch_dir,
                                     manifest_path,
                                     runtime):
        pass

    @staticmethod
    def _parse_builder_response(stdout_data, image_name):
        pass
```


``.samrc`` Changes
------------------
*Explain the new configuration entries, if any, you want to add to .samrc*

N/A

Security
--------

*Tip: How does this change impact security? Answer the following questions to help answer this question better:*

**What new dependencies (libraries/cli) does this change require?**

No new dependencies being added.

**What other Docker container images are you using?**

No need containers are being added.

**Are you creating a new HTTP endpoint? If so explain how it will be created & used**

N/A

**Are you connecting to a remote API? If so explain how is this connection secured**

No

**Are you reading/writing to a temporary folder? If so, what is this used for and when do you clean up?**

**How do you validate new .samrc configuration?**

N/A


Documentation Changes
---------------------

Open Issues
-----------

Task Breakdown
--------------
- [x] Send a Pull Request with this design document
- [ ] Build the command line interface
- [ ] Build the underlying library
- [ ] Unit tests
- [ ] Functional Tests
- [ ] Integration tests
- [ ] Run all tests on Windows
- [ ] Update documentation
