"""
Builds the application
"""

import os
import io
import json
import logging

from samcli.local.docker.lambda_build_container import LambdaBuildContainer
from aws_lambda_builders.builder import LambdaBuilder
from aws_lambda_builders.exceptions import LambdaBuilderError


LOG = logging.getLogger(__name__)


class UnsupportedRuntimeException(Exception):
    pass


class BuildError(Exception):
    pass


class ApplicationBuilder(object):
    """
    Class to build an entire application. Currently, this class builds Lambda functions only, but there is nothing that
    is stopping this class from supporting other resource types. Building in context of Lambda functions refer to
    converting source code into artifacts that can be run on AWS Lambda
    """

    _builder_capabilities = {
        "python2.7": {
            "language": "python",
            "dependency_manager": "pip",
            "application_framework": None,
            "manifest_name": "requirements.txt"
        },
        "python3.6": {
           "language": "python",
           "dependency_manager": "pip",
           "application_framework": None,
           "manifest_name": "requirements.txt"
        }
    }

    def __init__(self,
                 function_provider,
                 build_dir,
                 base_dir,
                 manifest_path_override=None,
                 container_manager=None,
                 parallel=False):
        """
        Initialize the class

        Parameters
        ----------
        function_provider : samcli.commands.local.lib.sam_function_provider.SamFunctionProvider
            Provider that can vend out functions available in the SAM template

        build_dir : str
            Path to the directory where we will be storing built artifacts

        base_dir : str
            Path to a folder. Use this folder as the root to resolve relative source code paths against

        container_manager : samcli.local.docker.manager.ContainerManager
            Optional. If provided, we will attempt to build inside a Docker Container

        parallel : bool
            Optional. Set to True to build each function in parallel to improve performance
        """
        self.function_provider = function_provider
        self.build_dir = build_dir
        self.base_dir = base_dir
        self.manifest_path_override = manifest_path_override

        self.container_manager = container_manager
        self.parallel = parallel

    def build(self):
        """
        Build the entire application

        Returns
        -------
        dict
            Returns the path to where each resource was built as a map of resource's LogicalId to the path string
        """

        result = {}

        for lambda_function in self.function_provider.get_all():

            if lambda_function.runtime not in self._builder_capabilities:
                raise UnsupportedRuntimeException("'%s' runtime is not supported".format(lambda_function.runtime))

            result[lambda_function.name] = self._build_function(lambda_function.name,
                                                                lambda_function.codeuri,
                                                                lambda_function.runtime)

        return result

    def update_template(self, template_dict, target_template_path, built_artifacts):
        """
        Given the path to built artifacts, update the template to point appropriate resource CodeUris to the artifacts
        folder

        Parameters
        ----------
        template_dict
        built_artifacts : dict
            Map of LogicalId of a resource to the path where the the built artifacts for this resource lives

        Returns
        -------
        dict
            Updated template
        """
        # TODO: Move this method to a "build provider" or some other class. It doesn't really fit within here.

        target_dir = os.path.dirname(target_template_path)

        for logical_id, resource in template_dict.get("Resources", {}).items():

            if logical_id not in built_artifacts:
                # this resource was not built. So skip it
                continue

            # Artifacts are written relative to the output template because it makes the template portability
            #   Ex: A CI/CD pipeline build stage could zip the output folder and pass to a
            #   package stage running on a different machine
            artifact_relative_path = os.path.relpath(built_artifacts[logical_id], target_dir)

            resource_type = resource.get("Type")
            if resource_type == "AWS::Serverless::Function":
                template_dict["Resources"][logical_id]["Properties"]["CodeUri"] = artifact_relative_path

            if resource_type == "AWS::Lambda::Function":
                template_dict["Resources"][logical_id]["Properties"]["Code"] = artifact_relative_path

        return template_dict

    def _build_function(self, function_name, codeuri, runtime):

        capability = self._builder_capabilities[runtime]

        # Create the arguments to pass to the builder
        code_dir = os.path.normpath(os.path.join(self.base_dir, codeuri))
        # artifacts directory will be created by the builder
        artifacts_dir = os.path.join(self.build_dir, function_name)

        # TODO: Create this
        scratch_dir = None

        # TODO: how do we let customers specify where the manifests are? Or change the name of the file?
        manifest_path = self.manifest_path_override or os.path.join(code_dir, capability["manifest_name"])

        if self.container_manager:
            return self._build_function_on_container(capability,
                                                     code_dir,
                                                     artifacts_dir,
                                                     manifest_path,
                                                     runtime)
        else:
            builder = LambdaBuilder(language=capability["language"],
                                    dependency_manager=capability["dependency_manager"],
                                    application_framework=capability["application_framework"])

            # TODO: Add try-catch and raise an internal exception if Workflow failed
            try:
                builder.build(code_dir,
                              artifacts_dir,
                              scratch_dir,
                              manifest_path,
                              runtime=runtime)
            except LambdaBuilderError as ex:
                raise BuildError(str(ex))

            return artifacts_dir

    def _build_function_on_container(self,
                                     capability,
                                     source_dir,
                                     artifacts_dir,
                                     manifest_path,
                                     runtime):

        # If we are printing debug logs in SAM CLI, the builder library should also print debug logs
        log_level = LOG.getEffectiveLevel()

        container = LambdaBuildContainer(capability["language"],
                                         capability["dependency_manager"],
                                         capability["application_framework"],
                                         source_dir,
                                         manifest_path,
                                         runtime,
                                         log_level=log_level)

        self.container_manager.run(container)

        stdout_stream = io.BytesIO()
        stderr_stream = io.BytesIO()
        container.wait_for_logs(stdout=stdout_stream, stderr=stderr_stream)

        stdout_data = stdout_stream.getvalue().decode('utf-8')
        logs = stderr_stream.getvalue().decode('utf-8')
        if logs:
            LOG.info("%s", logs)

        LOG.debug("Build inside container returned response %s", stdout_data)
        response = json.loads(stdout_data)

        if "error" in response:

            err_code = response["error"]["code"]
            if err_code == 400:
                # Like HTTP 4xx - customer error
                raise BuildError(response["error"]["message"])
            else:
                LOG.debug("Builder crashed")
                raise ValueError(response["error"]["message"])

        # Request is successful. Now copy the artifacts back to the host

        # "/." is a Docker thing that instructions the copy command to download contents of the folder only
        result_dir_in_container = response["result"]["artifacts_dir"] + "/."
        container.copy(result_dir_in_container, artifacts_dir)

        LOG.debug("Build inside container succeeded")
        return artifacts_dir
