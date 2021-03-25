"""
The plugin's preprocessor creates the required AWS resources for this pipeline if not already provided by the user.
"""
import logging
import os
import pathlib
from typing import Dict, List, Optional, Tuple

import click

from samcli.commands._utils.template import get_template_function_runtimes
from samcli.lib.cookiecutter.processor import Processor
from samcli.lib.utils.managed_cloudformation_stack import manage_stack as manage_cloudformation_stack
from samcli.local.common.runtime_template import RUNTIME_TO_BUILD_IMAGE
from .config import PLUGIN_NAME
from .context import Context as PluginContext
from .resource import Deployer
from .stage import Stage

ROOT_PATH = str(pathlib.Path(os.path.dirname(__file__)))
CFN_TEMPLATE_PATH = os.path.join(ROOT_PATH, "cfn_templates")
STACK_NAME_PREFIX = "aws-sam-cli-managed"
DEPLOYER_STACK_NAME_SUFFIX = "pipeline-deployer"
STAGE_RESOURCES_STACK_NAME_SUFFIX = "pipeline-resources"

LOG = logging.getLogger(__name__)


class Preprocessor(Processor):
    """
    1. Find the appropriate docker build image for the SAM temolate
    2. Creates the required AWS resources for this pipeline if not already provided by the user.

    Methods
    -------
    _get_build_image(sam_template_file) -> Optional[str]:
        scan the SAM template for the ZIP functions, extract the runtimes and return the appropriate SA< build image
        for the runtime if the template contains one and exactly one supported runtime, otherwise, asks the user
        to provide an alternative build-image
    run(context: Dict) -> Dict:
        Creates the missed required AWS resources and updated the passed cookiecutter context with its ARNs
    _create_deployer_at(stage: Stage):
        deploys the CFN template(./cfn_templates/deployer.yaml) to the given stage
    _create_missing_stage_resources(stage: Stage, deployer_arn: str):
        deploys the CFN template(./cfn_templates/resource_stages.yaml) to the given stage
    """

    BASIC_PROVIDED_BUILD_IMAGE: str = "public.ecr.aws/sam/build-provided"

    def run(self, context: Dict) -> Dict:
        """
        searches the passed cookiecutter context for the pipeline's required AWS resources, identifies which resources
        are missing, create them through a CFN stack.
        This method create and add to the context a plugin-explicit context that contains all of the required
        AWS resources and additional plugin explicit attribute. This plugin-explicit context is not used in the
        cookiecutter template itself, instead, it is used by the postprocessor of this plugin.
        The method returns a mutated copy of the cookiecutter context that updates the context with the ARNs of the
        created resources.

        Parameters
        ----------
        context: Dict
            The cookiecutter context to look for the resources from.
        """
        context = context.copy()
        plugin_context: PluginContext = PluginContext(context)
        context[PLUGIN_NAME] = plugin_context

        context["build_image"] = plugin_context.build_image = Preprocessor._get_build_image(context["sam_template"])

        deployer: Deployer = plugin_context.deployer
        if deployer.is_user_provided:
            deployer_arn = deployer.arn
        else:
            # create deployer(IAM user) in the testing stage
            testing_stage: Stage = plugin_context.get_stage(PluginContext.TESTING_STAGE_NAME)
            deployer_arn, access_key_id, secret_access_key = Preprocessor._create_deployer_at(stage=testing_stage)
            context["deployer_arn"] = deployer.arn = deployer_arn
            deployer.access_key_id = access_key_id
            deployer.secret_access_key = secret_access_key

        for stage in plugin_context.stages:
            (
                deployer_role_arn,
                cfn_deployment_role_arn,
                artifacts_bucket_arn,
                kms_key_arn,
            ) = Preprocessor._create_missing_stage_resources(stage=stage, deployer_arn=deployer_arn)
            context[f"{stage.name}_deployer_role"] = stage.deployer_role.arn = deployer_role_arn
            context[f"{stage.name}_cfn_deployment_role"] = stage.cfn_deployment_role.arn = cfn_deployment_role_arn
            stage.artifacts_bucket.arn = artifacts_bucket_arn
            stage.artifacts_bucket.kms_key_arn = kms_key_arn
            # The cookiecutter context requires the name of the artifacts bucket instead of ots ARN
            context[f"{stage.name}_artifacts_bucket"] = stage.artifacts_bucket.name()

        return context

    # This method is a first iteration only to support the major usecase of having a SAM template with one supported
    # runtime
    # todo improve the experience to support Iamge lambda functions and lambda functions with different runtimes
    @staticmethod
    def _get_build_image(sam_template_file: str) -> str:
        """
        Scans the SAM template for lambda runtimes, and if it contains only one supported runtime, it returns
        the corresponding SAM build-image, otherwise, it asks the user to provide one

        Parameters
        ----------
        sam_template_file: str
            the path of the SAM template to scan for function's runtimes

        Returns: a docker build-image to use for the CICD pipeline
        """
        runtimes: List[str] = get_template_function_runtimes(template_file=sam_template_file)
        if not runtimes:
            return Preprocessor.BASIC_PROVIDED_BUILD_IMAGE
        elif len(runtimes) > 1:
            click.echo(
                "The SAM template defines multiple functions with different runtimes\n"
                "SAM doesn't have an appropriate docker build image for that, please provide one"
            )
            return click.prompt("Docker Build image")
        else:
            runtime = runtimes[0]
            build_image = RUNTIME_TO_BUILD_IMAGE.get(runtime)
            if not build_image:
                click.echo(
                    f"The SAM template defines functions of runtime {runtime} but SAM doesn't have a docker "
                    f"build-image for {runtime}, please provide one"
                )
                build_image = click.prompt("Docker Build image")
            return build_image

    @staticmethod
    def _create_deployer_at(stage: Stage) -> Tuple[str, str, str]:
        """
        Deploys the CFN template(./cfn_templates/deployer.yaml) which defines a deployer IAM user and credentials
        to the AWS account and region associated with the given stage. It will not redeploy the stack if already exists.

        Parameters
        ----------
        stage: Stage
            The pipeline stage to deploy the CFN template to its associated AWS account and region.

        Returns
        -------
        ARN, access_key_id and secret_access_key of the IAM user identified by the template
        """

        profile: str = stage.aws_profile
        region: str = stage.aws_region
        stack_name: str = f"{STACK_NAME_PREFIX}-{stage.stack_name}-{DEPLOYER_STACK_NAME_SUFFIX}"
        deployer_template_path: str = os.path.join(CFN_TEMPLATE_PATH, "deployer.yaml")
        with open(deployer_template_path, "r") as fp:
            deployer_template_body = fp.read()
        click.echo(f"Creating an IAM user for pipeline Deployment. Account: '{profile}' Region: '{region}'")
        outputs: List[Dict[str, str]] = manage_cloudformation_stack(
            stack_name=stack_name, profile=profile, region=region, template_body=deployer_template_body
        )
        deployer_arn: str = next(o for o in outputs if o.get("OutputKey") == "Deployer").get("OutputValue")
        access_key_id_arn: str = next(o for o in outputs if o.get("OutputKey") == "AccessKeyId").get("OutputValue")
        secret_access_key_arn: str = next(o for o in outputs if o.get("OutputKey") == "SecretAccessKey").get(
            "OutputValue"
        )
        return deployer_arn, access_key_id_arn, secret_access_key_arn

    @staticmethod
    def _create_missing_stage_resources(stage: Stage, deployer_arn: str) -> Tuple[str, str, str, Optional[str]]:
        """
        Deploys the CFN template(./cfn_templates/stage_resources.yaml) which defines:
            * Deployer execution IAM role
            * CloudFormation execution IAM role
            * Artifacts' S3 Bucket along with KMS encryption key
        to the AWS account and region associated with the given stage. It will not redeploy the stack if already exists.
        This CFN template accepts the ARNs of the resources as parameters and will not create a resource if already
        provided, this way we can conditionally create a resource only if the user didn't provide it

        Parameters
        ----------
        stage: Stage
            The pipeline stage to deploy the CFN template to its associated AWS account and region.
        deployer_arn: str
            The ARN of the deployer IAM user. This is used by the CFN template to give this IAM user permissions to
            assume the IAM roles.

        Returns
        -------
        ARNs of the deployer execution role, CLoudFormation execution role, artifacts S3 bucket and bucket KMS key.
        """

        if stage.did_user_provide_all_required_resources():
            LOG.info(f"All required resources for the {stage.name} stage exist, skipping creation.")
            return (
                stage.deployer_role.arn,
                stage.cfn_deployment_role.arn,
                stage.artifacts_bucket.arn,
                stage.artifacts_bucket.kms_key_arn,
            )
        missing_resources: str = ""
        if not stage.deployer_role.is_user_provided:
            missing_resources += "\n\tDeployer role."
        if not stage.cfn_deployment_role.is_user_provided:
            missing_resources += "\n\tCloudFormation deployment role."
        if not stage.artifacts_bucket.is_user_provided:
            missing_resources += "\n\tArtifacts bucket."
        LOG.info(f"Creating missing required resources for the {stage.name} stage: {missing_resources}")
        stage_resources_template_path: str = os.path.join(CFN_TEMPLATE_PATH, "stage_resources.yaml")
        stack_name: str = f"{STACK_NAME_PREFIX}-{stage.stack_name}-{STAGE_RESOURCES_STACK_NAME_SUFFIX}"
        with open(stage_resources_template_path, "r") as fp:
            stage_resources_template_body = fp.read()
        output: List[Dict[str, str]] = manage_cloudformation_stack(
            stack_name=stack_name,
            region=stage.aws_region,
            profile=stage.aws_profile,
            template_body=stage_resources_template_body,
            parameter_overrides={
                "DeployerArn": deployer_arn,
                "DeployerRoleArn": stage.deployer_role.arn,
                "CFNDeploymentRoleArn": stage.cfn_deployment_role.arn,
                "ArtifactsBucketArn": stage.artifacts_bucket.arn,
            },
        )

        deployer_role_arn: str = next(o for o in output if o.get("OutputKey") == "DeployerRole").get("OutputValue")
        cfn_deployment_role_arn: str = next(o for o in output if o.get("OutputKey") == "CFNDeploymentRole").get(
            "OutputValue"
        )
        artifacts_bucket_arn: str = next(o for o in output if o.get("OutputKey") == "ArtifactsBucket").get(
            "OutputValue"
        )
        try:
            artifacts_bucket_key_arn: str = next(o for o in output if o.get("OutputKey") == "ArtifactsBucketKey").get(
                "OutputValue"
            )
        except StopIteration:
            artifacts_bucket_key_arn = None

        return deployer_role_arn, cfn_deployment_role_arn, artifacts_bucket_arn, artifacts_bucket_key_arn
