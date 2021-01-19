"""
Class to manage all the prompts during a guided sam deploy
"""

import logging

import click
from click.types import FuncParamType
from click import prompt
from click import confirm

from samcli.commands._utils.options import _space_separated_list_func_type
from samcli.commands._utils.template import get_template_parameters, get_template_data, get_template_artifacts_format
from samcli.commands.deploy.code_signer_utils import (
    signer_config_per_function,
    extract_profile_name_and_owner_from_existing,
    prompt_profile_name,
    prompt_profile_owner,
)
from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.commands.deploy.guided_config import GuidedConfig
from samcli.commands.deploy.auth_utils import auth_per_resource, transform_template
from samcli.commands.deploy.utils import sanitize_parameter_overrides
from samcli.lib.config.samconfig import DEFAULT_ENV, DEFAULT_CONFIG_FILE_NAME
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.package.image_utils import tag_translation, NonLocalImageException
from samcli.lib.utils.colors import Colored
from samcli.lib.utils.packagetype import IMAGE

LOG = logging.getLogger(__name__)


class GuidedContext:
    def __init__(
        self,
        template_file,
        stack_name,
        s3_bucket,
        image_repository,
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
    ):
        self.template_file = template_file
        self.stack_name = stack_name
        self.s3_bucket = s3_bucket
        self.image_repository = image_repository
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
        self.guided_s3_prefix = None
        self.guided_region = None
        self.guided_profile = None
        self.signing_profiles = signing_profiles
        self._capabilities = None
        self._parameter_overrides = None
        self.start_bold = "\033[1m"
        self.end_bold = "\033[0m"
        self.color = Colored()
        self.transformed_resources = None

    @property
    def guided_capabilities(self):
        return self._capabilities

    @property
    def guided_parameter_overrides(self):
        return self._parameter_overrides

    # pylint: disable=too-many-statements
    def guided_prompts(self, parameter_override_keys):
        default_stack_name = self.stack_name or "sam-app"
        default_region = self.region or "us-east-1"
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
        input_parameter_overrides = self.prompt_parameters(
            parameter_override_keys, self.parameter_overrides_from_cmdline, self.start_bold, self.end_bold
        )
        image_repository = self.prompt_image_repository(
            parameter_overrides=sanitize_parameter_overrides(input_parameter_overrides)
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

        sanitized_parameter_overrides = sanitize_parameter_overrides(input_parameter_overrides)
        self.prompt_authorization(sanitized_parameter_overrides)
        self.prompt_code_signing_settings(sanitized_parameter_overrides)

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

        s3_bucket = manage_stack(profile=self.profile, region=region)
        click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")
        click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")

        self.guided_stack_name = stack_name
        self.guided_s3_bucket = s3_bucket
        self.guided_image_repository = image_repository
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

    def prompt_authorization(self, parameter_overrides):
        auth_required_per_resource = auth_per_resource(parameter_overrides, get_template_data(self.template_file))

        for resource, authorization_required in auth_required_per_resource:
            if not authorization_required:
                auth_confirm = confirm(
                    f"\t{self.start_bold}{resource} may not have authorization defined, Is this okay?{self.end_bold}",
                    default=False,
                )
                if not auth_confirm:
                    raise GuidedDeployFailedError(msg="Security Constraints Not Satisfied!")

    def prompt_code_signing_settings(self, parameter_overrides):
        (functions_with_code_sign, layers_with_code_sign) = signer_config_per_function(
            parameter_overrides, get_template_data(self.template_file)
        )

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

    def prompt_image_repository(self, parameter_overrides):
        image_repository = None
        artifacts_format = get_template_artifacts_format(template_file=self.template_file)
        if IMAGE in artifacts_format:
            self.transformed_resources = transform_template(
                parameter_overrides=parameter_overrides,
                template_dict=get_template_data(template_file=self.template_file),
            )
            image_repository = prompt(
                f"\t{self.start_bold}Image Repository{self.end_bold}",
                type=click.STRING,
                default=self.image_repository if self.image_repository else "",
            )
            for _, function_prop in self.transformed_resources.functions.items():
                if function_prop.packagetype == IMAGE:
                    image = function_prop.imageuri
                    try:
                        tag = tag_translation(image)
                    except NonLocalImageException:
                        pass
                    else:
                        click.secho(f"\t{self.start_bold}Images that will be pushed:{self.end_bold}")
                        click.secho(f"\t  {image} to {image_repository}:{tag}")
            click.secho(nl=True)

        return image_repository

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
                image_repository=self.guided_image_repository,
                region=self.guided_region,
                profile=self.guided_profile,
                confirm_changeset=self.confirm_changeset,
                capabilities=self._capabilities,
                signing_profiles=self.signing_profiles,
            )

    def _get_parameter_value(self, parameter_key, parameter_properties, parameter_override_from_cmdline):
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
