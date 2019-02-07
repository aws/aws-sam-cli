sam build - artifacts
====================================

This is the design for debug artifacts that are produced everytime a Lambda function is built using `sam build`.

What is the problem?
--------------------

When debugging a sam application from within the docker container through an IDE interface, its imperative to know where the source code artifacts have been mounted to within the docker container. Even though the application is stopped within the docker container on debug breakpoint, we step through line by line on the IDE on the source that is local to the computer and not the docker container.

The mapping between the local source and remote source is not explicit. Its rather implicit that the source code is always mounted onto `/var/task` within the docker container, and thats hidden within sam cli's codebase.

What will be changed?
---------------------

Once a function is built using `sam build`, a new artifact can be written to ```.aws-sam/build/<Function-Logical-id>/build.json```

The contents of ```build.json``` would be all the metadata that is known about building that particular function. AWS SAM CLI uses ```aws-lambda-builders``` under the hood to build functions specified in the template. Depending on the language of the function specified in the template, corresponding build workflow is chosen.

IDEs can now consume the build.json artifact, to setup the corresponding debug configs.

The metadata known are the following.

* Function Name
* Language
* Dependency Manager
* Application Framework
* Build Workflow Name
* Source Directory
* Artifacts Directory
* Scratch Directory
* Manifest File Path
* Lambda runtime

The metadata that can be constructed are local source path mappings to remote path mappings.
```
"path_mapping" : {
"source_dir" : "/var/task" 
}
```

### Structure of build.json

```json
{
   "function_name" : "a",
    "language" : "b",
    "dependency_manager": "c",
    "application_framework": "d",
    "build_workflow_name": "e",
    "build_workflow_actions": ["f","g","h"],
    "source_directory" : "i",
    "artifacts_directory" : "j",
    "scratch_directory": "k",
    "manifest_path" : "l",
    "runtime": "m",
    "path_mapping" : {
        "i": "/var/task"
        }
}    
```

Success criteria for the change
-------------------------------
* An artifact that is consumable by IDEs to determine a map between local source and remote source and plug that into corresponding IDE configurations.


User Experience Walkthrough
---------------------------
* A user can run `sam build` and then look at the artifacts that are created to help fill out their IDE debug configuration
* Start debugging based on IDE debug configuration dependent on the language.

Implementation
==============

CLI Changes
-----------

* No changes in the CLI itself

### Breaking Change

* No breaking changes

Design
------

The build function is determined in app_builder.py based on if the build is happening locally or in the container.


```
    def build(self):
        """
        Build the entire application

        Returns
        -------
        dict
            Returns the path to where each resource was built as a map of resource's LogicalId to the path string
        """

        result = {}

        for lambda_function in self._function_provider.get_all():

            LOG.info("Building resource '%s'", lambda_function.name)
            result[lambda_function.name] = self._build_function(lambda_function.name,
                                                                lambda_function.codeuri,
                                                                lambda_function.runtime)
            if result[lambda_function.name]:
                  # write json artifacts to ~/.aws-sam/<lambda-function-logical-id>/build.json
               self._build_artifacts(lambda_function)

        return result
```


`.samrc` Changes
----------------

* None

Security
--------

* What new dependencies (libraries/cli) does this change require?
  * N/A
* What other Docker container images are you using?
  * N/A
* Are you creating a new HTTP endpoint? If so explain how it will be
created & used
 * N/A
* Are you connecting to a remote API? If so explain how is this
connection secured
 * N/A
* Are you reading/writing to a temporary folder? If so, what is this
used for and when do you clean up?
 * Writing to a known file path, it will get over written everytime a build is run.
* How do you validate new .samrc configuration?
 * N/A


Documentation Changes
---------------------
* New artifacts being created on running `sam build`
 
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

