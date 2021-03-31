""" The plugin context """
from typing import Dict, List, Optional

from .resource import Deployer
from .stage import Stage


class Context:
    """
    The context of the plugin. it defines two pipeline stages; testing and prod,
    the deployer IAM user and additional required context.

    Attributes
    ----------
    stages: List[Stage]
        The stages of the pipeline; testing and prod
    deployer: Deployer
        Represents the IAM User that deploys the pipeline. The credentials(AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY) of this IAM user must be shared with the CICD provider.
    deployer_aws_access_key_id_variable_name: str
        The name of the CICD env variable that holds the value of the AWS_ACCESS_KEY_ID
    deployer_aws_secret_access_key_variable_name: str
        The name of the CICD env variable that holds the value of the AWS_SECRET_ACCESS_KEY


    Methods
    -------
    get_stage(stage_name: str): Stage:
        returns a stage by name
    deployer_permissions(): str
        returns a string representing the required IAM policies for the deployer IAM user
        to be able to deploy the pipeline
    """

    TESTING_STAGE_NAME: str = "testing"
    PROD_STAGE_NAME: str = "prod"

    def __init__(self, context: Dict[str, str]) -> None:
        """

        Parameters
        ----------
        context: dictionary of user's response to the questions defined in the ./questions.json file where
                 keys are questions' keys and values are user's answers
        """

        testing_stage: Stage = Stage(
            name=Context.TESTING_STAGE_NAME,
            aws_profile=context.get("testing_profile"),
            aws_region=context.get("testing_region"),
            stack_name=context.get("testing_stack_name"),
            deployer_role_arn=context.get("testing_deployer_role"),
            cfn_deployment_role_arn=context.get("testing_cfn_deployment_role"),
            artifacts_bucket_arn=context.get("testing_artifacts_bucket"),
        )

        prod_stage: Stage = Stage(
            name=Context.PROD_STAGE_NAME,
            aws_profile=context.get("prod_profile"),
            aws_region=context.get("prod_region"),
            stack_name=context.get("prod_stack_name"),
            deployer_role_arn=context.get("prod_deployer_role"),
            cfn_deployment_role_arn=context.get("prod_cfn_deployment_role"),
            artifacts_bucket_arn=context.get("prod_artifacts_bucket"),
        )

        self.stages: List[Stage] = [testing_stage, prod_stage]
        self.deployer: Deployer = Deployer(arn=context.get("deployer_arn"))
        self.deployer_aws_access_key_id_variable_name: str = context.get("deployer_aws_access_key_id_variable_name")
        self.deployer_aws_secret_access_key_variable_name: str = context.get(
            "deployer_aws_secret_access_key_variable_name"
        )
        self.build_image: Optional[str] = None

    def get_stage(self, stage_name: str) -> Stage:
        """
        returns a stage by name.

        Parameters
        ----------
        stage_name: str
            The name of the stage to return
        """
        return next((stage for stage in self.stages if stage.name == stage_name), None)

    def deployer_permissions(self) -> str:
        """
        returns a string representing the required IAM policies for the deployer IAM user
        to be able to deploy the pipeline
        """
        deployer_roles = ", ".join(list(filter(None, map(lambda stage: stage.deployer_role.arn, self.stages))))
        permissions = f"""
{{
  "Effect": "Allow",
  "Action": ["sts:AssumeRole"],
  "Resource": [{deployer_roles}]
}}
        """
        return permissions
