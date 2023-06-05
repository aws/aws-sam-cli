""" Application Environment """
import hashlib
import json
import os
import pathlib
import re
import socket
from itertools import chain
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import boto3
import click
import requests
from botocore.exceptions import ClientError
from OpenSSL import SSL, crypto

from samcli.commands.pipeline.bootstrap.guided_context import BITBUCKET, GITHUB_ACTIONS, GITLAB, OPEN_ID_CONNECT
from samcli.commands.pipeline.bootstrap.pipeline_oidc_provider import PipelineOidcProvider
from samcli.lib.config.samconfig import SamConfig
from samcli.lib.pipeline.bootstrap.resource import ECRImageRepository, IAMUser, OidcProvider, Resource
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.managed_cloudformation_stack import StackOutput, update_stack

CFN_TEMPLATE_PATH = str(pathlib.Path(os.path.dirname(__file__)))
STACK_NAME_PREFIX = "aws-sam-cli-managed"
STAGE_RESOURCES_STACK_NAME_SUFFIX = "pipeline-resources"
STAGE_RESOURCES_CFN_TEMPLATE = "stage_resources.yaml"
PIPELINE_USER = "pipeline_user"
PIPELINE_EXECUTION_ROLE = "pipeline_execution_role"
CLOUDFORMATION_EXECUTION_ROLE = "cloudformation_execution_role"
ARTIFACTS_BUCKET = "artifacts_bucket"
ECR_IMAGE_REPOSITORY = "image_repository"
OIDC_PROVIDER_URL = "oidc_provider_url"
OIDC_CLIENT_ID = "oidc_client_id"
OIDC_PROVIDER = "oidc_provider"
GITHUB_ORG = "github_org"
GITHUB_REPO = "github_repo"
GITLAB_GROUP = "gitlab_group"
GITLAB_PROJECT = "gitlab_project"
DEPLOYMENT_BRANCH = "deployment_branch"
BITBUCKET_REPO_UUID = "bitbucket_repo_uuid"
PERMISSIONS_PROVIDER = "permissions_provider"
OIDC_SUPPORTED_PROVIDER = [GITHUB_ACTIONS, GITLAB, BITBUCKET]
REGION = "region"


def _get_secure_ssl_context() -> SSL.Context:
    """
    Returns a SSL Context with secure settings
    """
    ctx = SSL.Context(SSL.TLS_METHOD)
    ctx.set_options(SSL.OP_NO_TLSv1)
    ctx.set_options(SSL.OP_NO_TLSv1_1)
    ctx.set_options(SSL.OP_NO_SSLv2)
    ctx.set_options(SSL.OP_NO_SSLv3)
    return ctx


class Stage:
    """
    Represents an application stage: Beta, Gamma, Prod ...etc

    Attributes
    ----------
    name: str
        The name of the environment
    aws_profile: Optional[str]
        The named AWS profile (in user's machine) of the AWS account to deploy this environment to.
    aws_region: Optional[str]
        The AWS region to deploy this environment to.
    pipeline_user: IAMUser
        The IAM User having its AccessKeyId and SecretAccessKey credentials shared with the CI/CD system
    pipeline_execution_role: Resource
        The IAM role assumed by the pipeline-user to get access to the AWS account and executes the
        CloudFormation stack.
    cloudformation_execution_role: Resource
        The IAM role assumed by the CloudFormation service to executes the CloudFormation stack.
    artifacts_bucket: Resource
        The S3 bucket to hold the SAM build artifacts of the application's CFN template.
    create_image_repository: bool
        A boolean flag that determines whether the user wants to create an ECR image repository or not
    image_repository: ECRImageRepository
        The ECR image repository to hold the image container of lambda functions with Image package-type
    oidc_provider: OidcProvider
        The OIDCProvider to be created/used for assuming the pipeline execution role
    subject_claim: Optional[str]
        The subject claim that will be returned by the OIDC Provider to assume the role

    Methods:
    --------
    did_user_provide_all_required_resources(self) -> bool:
        checks if all of the environment's required resources (pipeline_user, pipeline_execution_role,
        cloudformation_execution_role, artifacts_bucket and image_repository) are provided by the user.
    bootstrap(self, confirm_changeset: bool = True) -> None:
        deploys the CFN template ./stage_resources.yaml to the AWS account identified by aws_profile and
        aws_region member fields. if aws_profile is not provided, it will fallback to  default boto3 credentials'
        resolving. Note that ./stage_resources.yaml template accepts the ARNs of already existing resources(if
        any) as parameters and it will skip the creation of those resources but will use the ARNs to set the proper
        permissions of other missing resources(resources created by the template)
    save_config(self, config_dir: str, filename: str, cmd_names: List[str]):
        save the Artifacts bucket name, ECR image repository URI and ARNs of pipeline_user, pipeline_execution_role and
        cloudformation_execution_role to the "pipelineconfig.toml" file so that it can be auto-filled during
        the `sam pipeline init` command.
    print_resources_summary(self) -> None:
        prints to the screen(console) the ARNs of the created and provided resources.
    _should_create_new_provider(self) -> bool:
        checks if there are any existing OIDC Providers configured in IAM by getting a list of all OIDC Providers
        setup in the account and seeing if the URL provided is in the ARN
    generate_thumbprint(oidc_provider_url) -> Optional[str]:
        retrieves the certificate of the top intermidate cerficate authority that signed the certificate
        used by the external identity provider and then returns the SHA1 hash of it. For more information on
        why the thumbprint is needed and the steps required to obtain it see the following page
        https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc_verify-thumbprint.html
    """

    def __init__(
        self,
        name: str,
        permissions_provider: Optional[str] = None,
        aws_profile: Optional[str] = None,
        aws_region: Optional[str] = None,
        pipeline_user_arn: Optional[str] = None,
        pipeline_execution_role_arn: Optional[str] = None,
        cloudformation_execution_role_arn: Optional[str] = None,
        artifacts_bucket_arn: Optional[str] = None,
        create_image_repository: bool = False,
        image_repository_arn: Optional[str] = None,
        oidc_provider_url: Optional[str] = None,
        oidc_client_id: Optional[str] = None,
        subject_claim: Optional[str] = None,
        pipeline_oidc_provider: Optional[PipelineOidcProvider] = None,
    ) -> None:
        self.name: str = name
        self.create_new_oidc_provider = False
        self.subject_claim = subject_claim
        self.use_oidc_provider = permissions_provider == OPEN_ID_CONNECT
        self.pipeline_oidc_provider = pipeline_oidc_provider
        self.aws_profile: Optional[str] = aws_profile
        self.aws_region: Optional[str] = aws_region
        self.pipeline_user: IAMUser = IAMUser(arn=pipeline_user_arn, comment="Pipeline IAM user")
        self.pipeline_execution_role: Resource = Resource(
            arn=pipeline_execution_role_arn, comment="Pipeline execution role"
        )
        self.cloudformation_execution_role: Resource = Resource(
            arn=cloudformation_execution_role_arn, comment="CloudFormation execution role"
        )
        self.artifacts_bucket: Resource = Resource(arn=artifacts_bucket_arn, comment="Artifact bucket")
        self.create_image_repository: bool = create_image_repository
        self.image_repository: ECRImageRepository = ECRImageRepository(
            arn=image_repository_arn, comment="ECR image repository"
        )
        self.color = Colored()

        self.oidc_provider: OidcProvider = OidcProvider(
            client_id=oidc_client_id,
            provider_url=oidc_provider_url,
            thumbprint="",
            comment="IAM OIDC Identity Provider",
            arn="",
        )

    def _should_create_new_provider(self, stack_name: str) -> bool:
        """
        Checks if there is an existing Identity Provider in the account already
        whos ARN contains the URL provided by the user.

        OIDC Provider arns are of the following format
        arn:aws:iam:::oidc-provider/api.bitbucket.org/2.0/workspaces//pipelines-config/identity/oidc
        we can check if the URL provided is already in an existing provider to see if a new one should be made
        -------
        """
        if not self.oidc_provider.provider_url:
            return False
        session = boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)
        iam_client = session.client("iam")
        cfn_client = session.client("cloudformation")
        providers = iam_client.list_open_id_connect_providers()

        url_to_compare = self.oidc_provider.provider_url.replace("https://", "")
        for provider_resource in providers["OpenIDConnectProviderList"]:
            if url_to_compare in provider_resource["Arn"]:
                try:
                    stack_res = cfn_client.describe_stack_resource(
                        StackName=stack_name, LogicalResourceId="OidcProvider"
                    )
                    return url_to_compare in stack_res["StackResourceDetail"]["PhysicalResourceId"]
                except ClientError as ex:
                    if "does not exist" in str(ex):
                        return False
                    raise ex
        return True

    @staticmethod
    def generate_thumbprint(oidc_provider_url: Optional[str]) -> Optional[str]:
        """
        retrieves the certificate of the top intermidate cerficate authority that signed the certificate
        used by the external identity provider and then returns the SHA1 hash of it. For more information on
        why the thumbprint is needed and the steps required to obtain it see the following page
        https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc_verify-thumbprint.html
        -------
        oidc_provider_url : Optional[str]
            The URL of the OIDC provider that will be used for authentication.
        """
        # Send HTTP GET to retrieve jwks_uri field from openid-configuration document
        oidc_config_url = "{url}/.well-known/openid-configuration".format(url=oidc_provider_url)
        r = requests.get(oidc_config_url, timeout=5)
        jwks_uri = r.json()["jwks_uri"]
        url_for_certificate = urlparse(jwks_uri).hostname

        # Create connection to retrieve certificate
        # Create an IPV4 socket and use TLS for the SSL connection
        address = (url_for_certificate, 443)
        ctx = _get_secure_ssl_context()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(address)
        c = SSL.Connection(ctx, s)
        c.set_connect_state()
        # set the servername extension becuase not setting it can cause errors with some sites
        c.set_tlsext_host_name(str.encode(address[0]))

        # If we attempt to get the cert chain without exchanging some traffic it will be empty
        c.sendall(str.encode("HEAD / HTTP/1.0\n\n"))
        peerCertChain = c.get_peer_cert_chain()
        cert = peerCertChain[-1]  # type: ignore

        # Dump the certificate in DER/ASN1 format so that its SHA1 hash can be computed
        dumped_cert = crypto.dump_certificate(crypto.FILETYPE_ASN1, cert)
        s.close()

        return hashlib.sha1(dumped_cert).hexdigest()

    def did_user_provide_all_required_resources(self) -> bool:
        """Check if the user provided all of the environment resources or not"""
        return all(resource.is_user_provided for resource in self._get_resources())

    def _get_non_user_provided_resources_msg(self) -> str:
        resource_comments = chain.from_iterable(
            [
                [] if self.pipeline_user.is_user_provided or self.use_oidc_provider else [self.pipeline_user.comment],
                [] if not self.use_oidc_provider else [self.oidc_provider.comment],
                [] if self.pipeline_execution_role.is_user_provided else [self.pipeline_execution_role.comment],
                []
                if self.cloudformation_execution_role.is_user_provided
                else [self.cloudformation_execution_role.comment],
                [] if self.artifacts_bucket.is_user_provided else [self.artifacts_bucket.comment],
                []
                if self.image_repository.is_user_provided or not self.create_image_repository
                else [self.image_repository.comment],
            ]
        )
        return "\n".join([f"\t- {comment}" for comment in resource_comments])

    def bootstrap(self, confirm_changeset: bool = True) -> bool:
        """
        Deploys the CFN template(./stage_resources.yaml) which deploys:
            * Pipeline IAM User or IAM OIDC Identity Provider
            * Pipeline execution IAM role
            * CloudFormation execution IAM role
            * Artifacts' S3 Bucket
            * ECR image repository
        to the AWS account associated with the given environment. It will not redeploy the stack if already exists.
        This CFN template accepts the ARNs of the resources as parameters and will not create a resource if already
        provided, this way we can conditionally create a resource only if the user didn't provide it

        THIS METHOD UPDATES THE STATE OF THE CALLING INSTANCE(self) IT WILL SET THE VALUES OF THE RESOURCES ATTRIBUTES

        Parameters
        ----------
        confirm_changeset: bool
            if set to false, the stage_resources.yaml CFN template will directly be deployed, otherwise,
            the user will be prompted for confirmation

        Returns True if bootstrapped, otherwise False
        """

        if self.did_user_provide_all_required_resources():
            click.secho(
                self.color.yellow(
                    f"\nAll required resources for the {self.name} configuration exist, skipping creation."
                )
            )
            return True

        missing_resources_msg: str = self._get_non_user_provided_resources_msg()
        click.echo(
            f"This will create the following required resources for the '{self.name}' configuration: \n"
            f"{missing_resources_msg}"
        )
        if confirm_changeset:
            confirmed: bool = click.confirm("Should we proceed with the creation?")
            if not confirmed:
                click.secho(self.color.red("Canceling pipeline bootstrap creation."))
                return False

        stack_name = self._get_stack_name()

        if self.use_oidc_provider:
            self.create_new_oidc_provider = self._should_create_new_provider(stack_name)
            if self.create_new_oidc_provider:
                self.oidc_provider.thumbprint = self.generate_thumbprint(self.oidc_provider.provider_url)

        environment_resources_template_body = Stage._read_template(STAGE_RESOURCES_CFN_TEMPLATE)
        output: StackOutput = update_stack(
            stack_name=stack_name,
            region=self.aws_region,
            profile=self.aws_profile,
            template_body=environment_resources_template_body,
            parameter_overrides={
                "PipelineUserArn": self.pipeline_user.arn or "",
                "PipelineExecutionRoleArn": self.pipeline_execution_role.arn or "",
                "CloudFormationExecutionRoleArn": self.cloudformation_execution_role.arn or "",
                "ArtifactsBucketArn": self.artifacts_bucket.arn or "",
                "CreateImageRepository": "true" if self.create_image_repository else "false",
                "ImageRepositoryArn": self.image_repository.arn or "",
                "IdentityProviderThumbprint": self.oidc_provider.thumbprint or "",
                "OidcClientId": self.oidc_provider.client_id or "",
                "OidcProviderUrl": self.oidc_provider.provider_url or "",
                "UseOidcProvider": "true" if self.use_oidc_provider else "false",
                "SubjectClaim": self.subject_claim or "",
                "CreateNewOidcProvider": "true" if self.create_new_oidc_provider else "false",
            },
        )

        if not self.use_oidc_provider:
            pipeline_user_secret_sm_id = output.get("PipelineUserSecretKey")

            self.pipeline_user.arn = output.get("PipelineUser")
            if pipeline_user_secret_sm_id:
                (
                    self.pipeline_user.access_key_id,
                    self.pipeline_user.secret_access_key,
                ) = Stage._get_pipeline_user_secret_pair(pipeline_user_secret_sm_id, self.aws_profile, self.aws_region)
        self.pipeline_execution_role.arn = output.get("PipelineExecutionRole")
        self.cloudformation_execution_role.arn = output.get("CloudFormationExecutionRole")
        self.artifacts_bucket.arn = output.get("ArtifactsBucket")
        self.image_repository.arn = output.get("ImageRepository")
        return True

    @staticmethod
    def _get_pipeline_user_secret_pair(
        secret_manager_arn: str, profile: Optional[str], region: Optional[str]
    ) -> Tuple[str, str]:
        """
        Helper method to fetch pipeline user's AWS Credentials from secrets manager.
        SecretString need to be in following JSON format:
        {
          "aws_access_key_id": "AWSSECRETACCESSKEY123",
          "aws_secret_access_key": "mYSuperSecretDummyKey"
        }
        Parameters
        ----------
        secret_manager_arn:
            ARN of secret manager entry which holds pipeline user key.
        profile:
            The named AWS profile (in user's machine) of the AWS account to deploy this environment to.
        region:
            The AWS region to deploy this environment to.

        Returns tuple of aws_access_key_id and aws_secret_access_key.

        """
        session = boto3.Session(profile_name=profile, region_name=region if region else None)
        secrets_manager_client = session.client("secretsmanager")
        response = secrets_manager_client.get_secret_value(SecretId=secret_manager_arn)
        secret_string = response["SecretString"]
        secret_json = json.loads(secret_string)
        return secret_json["aws_access_key_id"], secret_json["aws_secret_access_key"]

    @staticmethod
    def _read_template(template_file_name: str) -> str:
        template_path: str = os.path.join(CFN_TEMPLATE_PATH, template_file_name)
        with open(template_path, "r", encoding="utf-8") as fp:
            template_body = fp.read()
        return template_body

    def save_config(self, config_dir: str, filename: str, cmd_names: List[str]) -> None:
        """
        save the Artifacts bucket name, ECR image repository URI and ARNs of pipeline_user, pipeline_execution_role and
        cloudformation_execution_role to the given filename and directory.

        Parameters
        ----------
        config_dir: str
            the directory of the toml file to save to
        filename: str
            the name of the toml file to save to
        cmd_names: List[str]
            nested command name to scope the saved configs to inside the toml file

        Raises
        ------
        ValueError: if the artifacts_bucket or ImageRepository ARNs are invalid
        """

        samconfig: SamConfig = SamConfig(config_dir=config_dir, filename=filename)

        if self.pipeline_user.arn:
            samconfig.put(cmd_names=cmd_names, section="parameters", key=PIPELINE_USER, value=self.pipeline_user.arn)
            samconfig.put(cmd_names=cmd_names, section="parameters", key=PERMISSIONS_PROVIDER, value="AWS IAM")
        if self.use_oidc_provider and self.pipeline_oidc_provider:
            self.pipeline_oidc_provider.save_values(cmd_names=cmd_names, section="parameters", samconfig=samconfig)

        # Computing Artifacts bucket name and ECR image repository URL may through an exception if the ARNs are wrong
        # Let's swallow such an exception to be able to save the remaining resources
        try:
            artifacts_bucket_name: Optional[str] = self.artifacts_bucket.name()
        except ValueError:
            artifacts_bucket_name = ""
        try:
            image_repository_uri: Optional[str] = self.image_repository.get_uri() or ""
        except ValueError:
            image_repository_uri = ""

        environment_specific_configs: Dict[str, Optional[str]] = {
            PIPELINE_EXECUTION_ROLE: self.pipeline_execution_role.arn,
            CLOUDFORMATION_EXECUTION_ROLE: self.cloudformation_execution_role.arn,
            ARTIFACTS_BUCKET: artifacts_bucket_name,
            # even image repository can be None, we want to save it as empty string
            # so that pipeline init command can pick it up
            ECR_IMAGE_REPOSITORY: image_repository_uri,
            REGION: self.aws_region,
        }

        for key, value in environment_specific_configs.items():
            if value is not None:
                samconfig.put(
                    cmd_names=cmd_names,
                    section="parameters",
                    key=key,
                    value=value,
                    env=self.name,
                )

        samconfig.flush()

    def save_config_safe(self, config_dir: str, filename: str, cmd_names: List[str]) -> None:
        """
        A safe version of save_config method that doesn't raise any exception
        """
        try:
            self.save_config(config_dir, filename, cmd_names)
        except Exception:
            pass

    def _get_resources(self) -> List[Resource]:
        resources = [
            self.pipeline_execution_role,
            self.cloudformation_execution_role,
            self.artifacts_bucket,
        ]
        if self.use_oidc_provider:
            resources.append(self.oidc_provider)
        else:
            resources.append(self.pipeline_user)
        if self.create_image_repository or self.image_repository.arn:  # Image Repository is optional
            resources.append(self.image_repository)
        return resources

    def print_resources_summary(self) -> None:
        """prints to the screen(console) the ARNs of the created and provided resources."""

        provided_resources = []
        created_resources = []
        for resource in self._get_resources():
            if resource.is_user_provided:
                provided_resources.append(resource)
            else:
                created_resources.append(resource)

        if created_resources:
            click.secho(self.color.green("The following resources were created in your account:"))
            for resource in created_resources:
                click.secho(self.color.green(f"\t- {resource.comment}"))

        if not self.pipeline_user.is_user_provided and not self.use_oidc_provider:
            click.secho(self.color.green("Pipeline IAM user credential:"))
            click.secho(self.color.green(f"\tAWS_ACCESS_KEY_ID: {self.pipeline_user.access_key_id}"))
            click.secho(self.color.green(f"\tAWS_SECRET_ACCESS_KEY: {self.pipeline_user.secret_access_key}"))

    def _get_stack_name(self) -> str:
        sanitized_stage_configuration_name: str = re.sub("[^0-9a-zA-Z]+", "-", self.name)
        return f"{STACK_NAME_PREFIX}-{sanitized_stage_configuration_name}-{STAGE_RESOURCES_STACK_NAME_SUFFIX}"
