"""
Class to manage all the prompts during a guided sam deploy
"""

import logging
from typing import Dict, Any, List, Optional

import click
from click import confirm
from click import prompt
from click.types import FuncParamType

from samcli.commands._utils.options import _space_separated_list_func_type
from samcli.commands._utils.template import (
    get_template_parameters,
)
from samcli.commands.deploy.auth_utils import auth_per_resource
from samcli.commands.deploy.code_signer_utils import (
    signer_config_per_function,
    extract_profile_name_and_owner_from_existing,
    prompt_profile_name,
    prompt_profile_owner,
)
from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.commands.deploy.guided_config import GuidedConfig
from samcli.commands.deploy.utils import sanitize_parameter_overrides
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.config.samconfig import DEFAULT_ENV, DEFAULT_CONFIG_FILE_NAME
from samcli.lib.intrinsic_resolver.intrinsics_symbol_table import IntrinsicsSymbolTable
from samcli.lib.package.ecr_utils import is_ecr_url
from samcli.lib.package.image_utils import tag_translation, NonLocalImageException, NoImageFoundException
from samcli.lib.providers.provider import Function, Stack, get_resource_full_path_by_id, ResourceIdentifier
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.defaults import get_default_aws_region
from samcli.lib.utils.packagetype import IMAGE
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.bootstrap.companion_stack.companion_stack_manager import CompanionStackManager

LOG = logging.getLogger(__name__)


class GuidedContext:
    # pylint: disable=too-many-statements
    def __init__(
        self,
        template_file,
        stack_name,
        s3_bucket,
        image_repository,
        image_repositories,
        s3_prefix,
        region=None,
        profile=None,
        confirm_changeset=None,
        capabilities=None,
        signing_profiles=None,
        parameter_overrides=None,
        save_to_config=True,
        config_section=None,
        config_env=None,
        config_file=None,
        disable_rollback=None,
    ):
        self.template_file = template_file
        self.stack_name = stack_name
        self.s3_bucket = s3_bucket
        self.image_repository = image_repository
        self.image_repositories = image_repositories
        self.s3_prefix = s3_prefix
        self.region = region
        self.profile = profile
        self.confirm_changeset = confirm_changeset
        self.capabilities = (capabilities,)
        self.parameter_overrides_from_cmdline = parameter_overrides
        self.save_to_config = save_to_config
        self.config_section = config_section
        self.config_env = config_env
        self.config_file = config_file
        self.guided_stack_name = None
        self.guided_s3_bucket = None
        self.guided_image_repository = None
        self.guided_image_repositories = None
        self.guided_s3_prefix = None
        self.guided_region = None
        self.guided_profile = None
        self.signing_profiles = signing_profiles
        self._capabilities = None
        self._parameter_overrides = None
        self.start_bold = "\033[1m"
        self.end_bold = "\033[0m"
        self.color = Colored()
        self.function_provider = None
        self.disable_rollback = disable_rollback

    @property
    def guided_capabilities(self):
        return self._capabilities

    @property
    def guided_parameter_overrides(self):
        return self._parameter_overrides

    # pylint: disable=too-many-statements
    def guided_prompts(self, parameter_override_keys):
        """
        Start an interactive cli prompt to collection information for deployment

        Parameters
        ----------
        parameter_override_keys
            The keys of parameters to override, for each key, customers will be asked to provide a value
        """
        default_stack_name = self.stack_name or "sam-app"
        default_region = self.region or get_default_aws_region()
        default_capabilities = self.capabilities[0] or ("CAPABILITY_IAM",)
        default_config_env = self.config_env or DEFAULT_ENV
        default_config_file = self.config_file or DEFAULT_CONFIG_FILE_NAME
        input_capabilities = None
        config_env = None
        config_file = None

        click.echo(
            self.color.yellow(
                "\n\tSetting default arguments for 'sam deploy'\n\t========================================="
            )
        )

        stack_name = prompt(
            f"\t{self.start_bold}Stack Name{self.end_bold}", default=default_stack_name, type=click.STRING
        )
        region = prompt(f"\t{self.start_bold}AWS Region{self.end_bold}", default=default_region, type=click.STRING)
        global_parameter_overrides = {IntrinsicsSymbolTable.AWS_REGION: region}
        input_parameter_overrides = self.prompt_parameters(
            parameter_override_keys, self.parameter_overrides_from_cmdline, self.start_bold, self.end_bold
        )
        stacks, _ = SamLocalStackProvider.get_stacks(
            self.template_file,
            parameter_overrides=sanitize_parameter_overrides(input_parameter_overrides),
            global_parameter_overrides=global_parameter_overrides,
        )

        click.secho("\t#Shows you resources changes to be deployed and require a 'Y' to initiate deploy")
        confirm_changeset = confirm(
            f"\t{self.start_bold}Confirm changes before deploy{self.end_bold}", default=self.confirm_changeset
        )
        click.secho("\t#SAM needs permission to be able to create roles to connect to the resources in your template")
        capabilities_confirm = confirm(
            f"\t{self.start_bold}Allow SAM CLI IAM role creation{self.end_bold}", default=True
        )

        if not capabilities_confirm:
            input_capabilities = prompt(
                f"\t{self.start_bold}Capabilities{self.end_bold}",
                default=list(default_capabilities),
                type=FuncParamType(func=_space_separated_list_func_type),
            )

        click.secho("\t#Preserves the state of previously provisioned resources when an operation fails")
        disable_rollback = confirm(f"\t{self.start_bold}Disable rollback{self.end_bold}", default=self.disable_rollback)

        self.prompt_authorization(stacks)
        self.prompt_code_signing_settings(stacks)

        save_to_config = confirm(
            f"\t{self.start_bold}Save arguments to configuration file{self.end_bold}", default=True
        )
        if save_to_config:
            config_file = prompt(
                f"\t{self.start_bold}SAM configuration file{self.end_bold}",
                default=default_config_file,
                type=click.STRING,
            )
            config_env = prompt(
                f"\t{self.start_bold}SAM configuration environment{self.end_bold}",
                default=default_config_env,
                type=click.STRING,
            )

        click.echo("\n\tLooking for resources needed for deployment:")
        s3_bucket = manage_stack(profile=self.profile, region=region)
        click.echo(f"\t Managed S3 bucket: {s3_bucket}")
        click.echo("\t A different default S3 bucket can be set in samconfig.toml")

        image_repositories = self.prompt_image_repository(
            stack_name, stacks, self.image_repositories, region, s3_bucket, self.s3_prefix
        )

        self.guided_stack_name = stack_name
        self.guided_s3_bucket = s3_bucket
        self.guided_image_repositories = image_repositories
        self.guided_s3_prefix = stack_name
        self.guided_region = region
        self.guided_profile = self.profile
        self._capabilities = input_capabilities if input_capabilities else default_capabilities
        self._parameter_overrides = (
            input_parameter_overrides if input_parameter_overrides else self.parameter_overrides_from_cmdline
        )
        self.save_to_config = save_to_config
        self.config_env = config_env if config_env else default_config_env
        self.config_file = config_file if config_file else default_config_file
        self.confirm_changeset = confirm_changeset
        self.disable_rollback = disable_rollback

    def prompt_authorization(self, stacks: List[Stack]):
        auth_required_per_resource = auth_per_resource(stacks)

        for resource, authorization_required in auth_required_per_resource:
            if not authorization_required:
                auth_confirm = confirm(
                    f"\t{self.start_bold}{resource} may not have authorization defined, Is this okay?{self.end_bold}",
                    default=False,
                )
                if not auth_confirm:
                    raise GuidedDeployFailedError(msg="Security Constraints Not Satisfied!")

    def prompt_code_signing_settings(self, stacks: List[Stack]):
        """
        Prompt code signing settings to ask whether customers want to code sign their code and
        display signing details.

        Parameters
        ----------
        stacks : List[Stack]
            List of stacks to search functions and layers
        """
        (functions_with_code_sign, layers_with_code_sign) = signer_config_per_function(stacks)

        # if no function or layer definition found with code signing, skip it
        if not functions_with_code_sign and not layers_with_code_sign:
            LOG.debug("No function or layer definition found with code sign config, skipping")
            return

        click.echo("\n\t#Found code signing configurations in your function definitions")
        sign_functions = confirm(
            f"\t{self.start_bold}Do you want to sign your code?{self.end_bold}",
            default=True,
        )

        if not sign_functions:
            LOG.debug("User skipped code signing, continuing rest of the process")
            self.signing_profiles = None
            return

        if not self.signing_profiles:
            self.signing_profiles = {}

        click.echo("\t#Please provide signing profile details for the following functions & layers")

        for function_name in functions_with_code_sign:
            (profile_name, profile_owner) = extract_profile_name_and_owner_from_existing(
                function_name, self.signing_profiles
            )

            click.echo(f"\t#Signing profile details for function '{function_name}'")
            profile_name = prompt_profile_name(profile_name, self.start_bold, self.end_bold)
            profile_owner = prompt_profile_owner(profile_owner, self.start_bold, self.end_bold)
            self.signing_profiles[function_name] = {"profile_name": profile_name, "profile_owner": profile_owner}
            self.signing_profiles[function_name]["profile_owner"] = "" if not profile_owner else profile_owner

        for layer_name, functions_use_this_layer in layers_with_code_sign.items():
            (profile_name, profile_owner) = extract_profile_name_and_owner_from_existing(
                layer_name, self.signing_profiles
            )
            click.echo(
                f"\t#Signing profile details for layer '{layer_name}', "
                f"which is used by functions {functions_use_this_layer}"
            )
            profile_name = prompt_profile_name(profile_name, self.start_bold, self.end_bold)
            profile_owner = prompt_profile_owner(profile_owner, self.start_bold, self.end_bold)
            self.signing_profiles[layer_name] = {"profile_name": profile_name, "profile_owner": profile_owner}
            self.signing_profiles[layer_name]["profile_owner"] = "" if not profile_owner else profile_owner

        LOG.debug("Signing profile names and owners %s", self.signing_profiles)

    def prompt_parameters(
        self, parameter_override_from_template, parameter_override_from_cmdline, start_bold, end_bold
    ):
        _prompted_param_overrides = {}
        if parameter_override_from_template:
            for parameter_key, parameter_properties in parameter_override_from_template.items():
                no_echo = parameter_properties.get("NoEcho", False)
                if no_echo:
                    parameter = prompt(
                        f"\t{start_bold}Parameter {parameter_key}{end_bold}", type=click.STRING, hide_input=True
                    )
                    _prompted_param_overrides[parameter_key] = {"Value": parameter, "Hidden": True}
                else:
                    parameter = prompt(
                        f"\t{start_bold}Parameter {parameter_key}{end_bold}",
                        default=_prompted_param_overrides.get(
                            parameter_key,
                            self._get_parameter_value(
                                parameter_key, parameter_properties, parameter_override_from_cmdline
                            ),
                        ),
                        type=click.STRING,
                    )
                    _prompted_param_overrides[parameter_key] = {"Value": parameter, "Hidden": False}
        return _prompted_param_overrides

    def prompt_image_repository(
        self,
        stack_name,
        stacks: List[Stack],
        image_repositories: Optional[Dict[str, str]],
        region: str,
        s3_bucket: str,
        s3_prefix: str,
    ) -> Dict[str, str]:
        """
        Prompt for the image repository to push the images.
        For each image function found in build artifacts, it will prompt for an image repository.

        Parameters
        ----------
        stack_name : List[Stack]
            Name of the stack to be deployed.

        stacks : List[Stack]
            List of stacks to look for image functions.

        image_repositories: Dict[str, str]
            Dictionary with function logical ID as key and image repo URI as value.

        region: str
            Region for the image repos.

        s3_bucket: str
            s3 bucket URI to be used for uploading companion stack template

        s3_prefix: str
            s3 prefix to be used for uploading companion stack template

        Returns
        -------
        Dict[str, str]
            A dictionary contains image function logical ID as key, image repository as value.
        """
        image_repositories = image_repositories if image_repositories is not None else {}
        updated_repositories = {}
        for image_repo_func_id, image_repo_uri in image_repositories.items():
            repo_full_path = get_resource_full_path_by_id(stacks, ResourceIdentifier(image_repo_func_id))
            if repo_full_path:
                updated_repositories[repo_full_path] = image_repo_uri
        self.function_provider = SamFunctionProvider(stacks, ignore_code_extraction_warnings=True)
        manager = CompanionStackManager(stack_name, region, s3_bucket, s3_prefix)

        function_logical_ids = [
            function.full_path for function in self.function_provider.get_all() if function.packagetype == IMAGE
        ]

        functions_without_repo = [
            function_logical_id
            for function_logical_id in function_logical_ids
            if function_logical_id not in updated_repositories
        ]

        manager.set_functions(function_logical_ids, updated_repositories)

        create_all_repos = self.prompt_create_all_repos(
            function_logical_ids, functions_without_repo, updated_repositories
        )
        if create_all_repos:
            updated_repositories.update(manager.get_repository_mapping())
        else:
            updated_repositories = self.prompt_specify_repos(functions_without_repo, updated_repositories)
            manager.set_functions(function_logical_ids, updated_repositories)

        updated_repositories = self.prompt_delete_unreferenced_repos(
            [manager.get_repo_uri(repo) for repo in manager.get_unreferenced_repos()], updated_repositories
        )
        GuidedContext.verify_images_exist_locally(self.function_provider.functions)

        manager.sync_repos()
        return updated_repositories

    def prompt_specify_repos(
        self,
        functions_without_repos: List[str],
        image_repositories: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Show prompts for each function that isn't associated with a image repo

        Parameters
        ----------
        functions_without_repos: List[str]
            List of functions without associating repos

        image_repositories: Dict[str, str]
            Current image repo dictionary with function logical ID as key and image repo URI as value.

        Returns
        -------
        Dict[str, str]
            Updated image repo dictionary with values(image repo URIs) filled by user input
        """
        updated_repositories = image_repositories.copy()
        for function_logical_id in functions_without_repos:
            image_uri = prompt(
                f"\t {self.start_bold}ECR repository for {function_logical_id}{self.end_bold}",
                type=click.STRING,
            )
            if not is_ecr_url(image_uri):
                raise GuidedDeployFailedError(f"Invalid Image Repository ECR URI: {image_uri}")

            updated_repositories[function_logical_id] = image_uri

        return updated_repositories

    def prompt_create_all_repos(
        self, functions: List[str], functions_without_repo: List[str], existing_mapping: Dict[str, str]
    ) -> bool:
        """
        Prompt whether to create all repos

        Parameters
        ----------
        functions: List[str]
            List of function logical IDs that are image based

        functions_without_repo: List[str]
            List of function logical IDs that do not have an ECR image repo specified

        existing_mapping: Dict[str, str]
            Current image repo dictionary with function logical ID as key and image repo URI as value.
            This dict will be shown in the terminal.

        Returns
        -------
        Boolean
            Returns False if there is no missing function or denied by prompt
        """
        if not functions:
            return False

        # Case for when all functions do not have mapped repo
        if functions == functions_without_repo:
            click.echo("\t Image repositories: Not found.")
            click.echo(
                "\t #Managed repositories will be deleted when "
                "their functions are removed from the template and deployed"
            )
            return confirm(
                f"\t {self.start_bold}Create managed ECR repositories for all functions?{self.end_bold}", default=True
            )

        functions_with_repo_count = len(functions) - len(functions_without_repo)
        click.echo(
            "\t Image repositories: "
            f"Found ({functions_with_repo_count} of {len(functions)})"
            " #Different image repositories can be set in samconfig.toml"
        )
        for function_logical_id, repo_uri in existing_mapping.items():
            click.echo(f"\t {function_logical_id}: {repo_uri}")

        # Case for all functions do have mapped repo
        if not functions_without_repo:
            return False

        click.echo(
            "\t #Managed repositories will be deleted when their functions are "
            "removed from the template and deployed"
        )
        return (
            confirm(
                f"\t {self.start_bold}Create managed ECR repositories for the "
                f"{len(functions_without_repo)} functions without?{self.end_bold}",
                default=True,
            )
            if functions_without_repo
            else True
        )

    def prompt_delete_unreferenced_repos(
        self, unreferenced_repo_uris: List[str], image_repositories: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Prompt user for deleting unreferenced companion stack image repos.
        Throws GuidedDeployFailedError if delete repos has been denied by the user.
        This function does not actually remove the functions from the stack.

        Parameters
        ----------

        unreferenced_repo_uris: List[str]
            List of unreferenced image repos that need to be deleted.
        image_repositories: Dict[str, str]
            Dictionary of image repo URIs with key as function logical ID and value as image repo URI

        Returns
        -------
        Dict[str, str]
            Copy of image_repositories that have unreferenced image repos removed
        """
        output_image_repositories = image_repositories.copy()

        if not unreferenced_repo_uris:
            return output_image_repositories

        click.echo("\t Checking for unreferenced ECR repositories to clean-up: " f"{len(unreferenced_repo_uris)} found")
        for repo_uri in unreferenced_repo_uris:
            click.echo(f"\t  {repo_uri}")
        delete_repos = confirm(
            f"\t {self.start_bold}Delete the unreferenced repositories listed above when deploying?{self.end_bold}",
            default=False,
        )
        if not delete_repos:
            click.echo("\t Deployment aborted!")
            click.echo(
                "\t #The deployment was aborted to prevent "
                "unreferenced managed ECR repositories from being deleted.\n"
                "\t #You may remove repositories from the SAMCLI "
                "managed stack to retain them and resolve this unreferenced check."
            )
            raise GuidedDeployFailedError("Unreferenced Auto Created ECR Repos Must Be Deleted.")

        for function_logical_id, repo_uri in image_repositories.items():
            if repo_uri in unreferenced_repo_uris:
                del output_image_repositories[function_logical_id]
                break
        return output_image_repositories

    @staticmethod
    def verify_images_exist_locally(functions: Dict[str, Function]) -> None:
        """
        Verify all images associated with deploying functions exist locally.

        Parameters
        ----------
        functions: Dict[str, Function]
            Dictionary of functions in the stack to be deployed with key as their logical ID.
        """
        for _, function_prop in functions.items():
            if function_prop.packagetype != IMAGE:
                continue
            image = function_prop.imageuri
            try:
                tag_translation(image)
            except NonLocalImageException:
                LOG.debug("Image URI is not pointing to local. Skipping verification.")
            except NoImageFoundException as ex:
                raise GuidedDeployFailedError("No images found to deploy, try running sam build") from ex

    def run(self):

        try:
            _parameter_override_keys = get_template_parameters(template_file=self.template_file)
        except ValueError as ex:
            LOG.debug("Failed to parse SAM template", exc_info=ex)
            raise GuidedDeployFailedError(str(ex)) from ex

        guided_config = GuidedConfig(template_file=self.template_file, section=self.config_section)
        guided_config.read_config_showcase(
            self.config_file or DEFAULT_CONFIG_FILE_NAME,
        )

        self.guided_prompts(_parameter_override_keys)

        if self.save_to_config:
            guided_config.save_config(
                self._parameter_overrides,
                self.config_env or DEFAULT_ENV,
                self.config_file or DEFAULT_CONFIG_FILE_NAME,
                stack_name=self.guided_stack_name,
                s3_bucket=self.guided_s3_bucket,
                s3_prefix=self.guided_s3_prefix,
                image_repositories=self.guided_image_repositories,
                region=self.guided_region,
                profile=self.guided_profile,
                confirm_changeset=self.confirm_changeset,
                capabilities=self._capabilities,
                signing_profiles=self.signing_profiles,
                disable_rollback=self.disable_rollback,
            )

    @staticmethod
    def _get_parameter_value(
        parameter_key: str, parameter_properties: Dict, parameter_override_from_cmdline: Dict
    ) -> Any:
        """
        This function provide the value of a parameter. If the command line/config file have "override_parameter"
        whose key exist in the template file parameters, it will use the corresponding value.
        Otherwise, it will use its default value in template file.

        :param parameter_key: key of parameter
        :param parameter_properties: properties of that parameters from template file
        :param parameter_override_from_cmdline: parameter_override from command line/config file
        """
        if parameter_override_from_cmdline and parameter_override_from_cmdline.get(parameter_key, None):
            return parameter_override_from_cmdline[parameter_key]
        # Make sure the default is casted to a string.
        return str(parameter_properties.get("Default", ""))
