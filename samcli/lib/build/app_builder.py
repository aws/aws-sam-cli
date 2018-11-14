"""
Builds the application
"""

import os
import shutil
from aws_lambda_builders.builder import LambdaBuilder


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

    def __init__(self, function_provider, build_dir, source_root, use_container=False, parallel=False):
        """
        Initialize the class

        Parameters
        ----------
        function_provider : samcli.commands.local.lib.sam_function_provider.SamFunctionProvider
            Provider that can vend out functions available in the SAM template

        build_dir : str
            Path to the directory where we will be storing built artifacts

        source_root : str
            Path to a folder. Use this folder as the root to resolve relative source code paths against

        use_container : bool
            Optional. Set to True if you want to run the builds on an container that simulates AWS Lambda environment

        parallel : bool
            Optional. Set to True to build each function in parallel to improve performance
        """
        self.function_provider = function_provider
        self.build_dir = build_dir
        self.source_root = source_root

        self.use_container = use_container
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
            result[lambda_function.name] = self._build_function(lambda_function.name,
                                                                lambda_function.codeuri,
                                                                lambda_function.runtime)

        return result

    def update_template(self, template_dict, built_artifacts):
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

        for logical_id, resource in template_dict.get("Resources", {}).items():

            if logical_id not in built_artifacts:
                # this resource was not built. So skip it
                continue

            resource_type = resource.get("Type")
            if resource_type == "AWS::Serverless::Function":
                template_dict["Resources"][logical_id]["Properties"]["CodeUri"] = built_artifacts[logical_id]

            if resource_type == "AWS::Lambda::Function":
                template_dict["Resources"][logical_id]["Properties"]["Code"] = built_artifacts[logical_id]

        return template_dict

    def _build_function(self, function_name, codeuri, runtime):

        capability = self._builder_capabilities[runtime]

        # Create the arguments to pass to the builder
        code_dir = os.path.normpath(os.path.join(self.source_root, codeuri))
        # artifacts directory will be created by the builder
        artifacts_dir = os.path.join(self.build_dir, function_name)

        # TODO: Create this
        scratch_dir = None

        # TODO: how do we let customers specify where the manifests are? Or change the name of the file?
        manifest_path = os.path.join(code_dir, capability["manifest_name"])

        builder = LambdaBuilder(language=capability["language"],
                                dependency_manager=capability["dependency_manager"],
                                application_framework=capability["application_framework"])

        builder.build(code_dir,
                      artifacts_dir,
                      scratch_dir,
                      manifest_path,
                      runtime=runtime)

        return artifacts_dir
