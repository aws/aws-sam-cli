"""
Class to manage all the prompts during a guided sam deploy
"""

import logging

import click
from click.types import FuncParamType
from click import prompt
from click import confirm

from samcli.commands._utils.options import _space_separated_list_func_type
from samcli.commands._utils.template import get_template_parameters, get_template_data
from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.commands.deploy.guided_config import GuidedConfig
from samcli.commands.deploy.auth_utils import auth_per_resource
from samcli.commands.deploy.utils import sanitize_parameter_overrides, print_deploy_args
from samcli.lib.bootstrap.bootstrap import manage_stack
from samcli.lib.utils.colors import Colored

LOG = logging.getLogger(__name__)


class GuidedContext:
    def __init__(
        self,
        template_file,
        stack_name,
        s3_bucket,
        s3_prefix,
        region=None,
        profile=None,
        confirm_changeset=None,
        capabilities=None,
        parameter_overrides=None,
        save_to_config=True,
        config_section=None,
    ):
        self.template_file = template_file
        self.stack_name = stack_name
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.region = region
        self.profile = profile
        self.confirm_changeset = confirm_changeset
        self.capabilities = (capabilities,)
        self.parameter_overrides = parameter_overrides
        self.save_to_config = save_to_config
        self.config_section = config_section
        self.guided_stack_name = None
        self.guided_s3_bucket = None
        self.guided_s3_prefix = None
        self.guided_region = None
        self.guided_profile = None
        self._capabilities = None
        self._parameter_overrides = None
        self.start_bold = "\033[1m"
        self.end_bold = "\033[0m"
        self.color = Colored()

    @property
    def guided_capabilities(self):
        return self._capabilities

    @property
    def guided_parameter_overrides(self):
        return self._parameter_overrides

    def guided_prompts(self, parameter_override_keys):
        default_stack_name = self.stack_name or "sam-app"
        default_region = self.region or "us-east-1"
        default_capabilities = self.capabilities[0] or ("CAPABILITY_IAM",)
        input_capabilities = None

        click.echo(
            self.color.yellow(
                "\n\tSetting default arguments for 'sam deploy'\n\t========================================="
            )
        )

        stack_name = prompt(
            f"\t{self.start_bold}Stack Name{self.end_bold}", default=default_stack_name, type=click.STRING
        )
        region = prompt(f"\t{self.start_bold}AWS Region{self.end_bold}", default=default_region, type=click.STRING)
        input_parameter_overrides = self.prompt_parameters(parameter_override_keys, self.start_bold, self.end_bold)

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

        self.prompt_authorization(sanitize_parameter_overrides(input_parameter_overrides))

        save_to_config = confirm(f"\t{self.start_bold}Save arguments to samconfig.toml{self.end_bold}", default=True)

        s3_bucket = manage_stack(profile=self.profile, region=region)
        click.echo(f"\n\t\tManaged S3 bucket: {s3_bucket}")
        click.echo("\t\tA different default S3 bucket can be set in samconfig.toml")

        self.guided_stack_name = stack_name
        self.guided_s3_bucket = s3_bucket
        self.guided_s3_prefix = stack_name
        self.guided_region = region
        self.guided_profile = self.profile
        self._capabilities = input_capabilities if input_capabilities else default_capabilities
        self._parameter_overrides = input_parameter_overrides if input_parameter_overrides else self.parameter_overrides
        self.save_to_config = save_to_config
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

    def prompt_parameters(self, parameter_override_keys, start_bold, end_bold):
        _prompted_param_overrides = {}
        if parameter_override_keys:
            for parameter_key, parameter_properties in parameter_override_keys.items():
                no_echo = parameter_properties.get("NoEcho", False)
                if no_echo:
                    parameter = prompt(
                        f"\t{start_bold}Parameter {parameter_key}{end_bold}", type=click.STRING, hide_input=True
                    )
                    _prompted_param_overrides[parameter_key] = {"Value": parameter, "Hidden": True}
                else:
                    # Make sure the default is casted to a string.
                    parameter = prompt(
                        f"\t{start_bold}Parameter {parameter_key}{end_bold}",
                        default=_prompted_param_overrides.get(
                            parameter_key, str(parameter_properties.get("Default", ""))
                        ),
                        type=click.STRING,
                    )
                    _prompted_param_overrides[parameter_key] = {"Value": parameter, "Hidden": False}
        return _prompted_param_overrides

    def run(self):

        try:
            _parameter_override_keys = get_template_parameters(template_file=self.template_file)
        except ValueError as ex:
            LOG.debug("Failed to parse SAM template", exc_info=ex)
            raise GuidedDeployFailedError(str(ex))

        guided_config = GuidedConfig(template_file=self.template_file, section=self.config_section)
        guided_config.read_config_showcase()

        self.guided_prompts(_parameter_override_keys)

        print_deploy_args(
            stack_name=self.guided_stack_name,
            s3_bucket=self.guided_s3_bucket,
            region=self.guided_region,
            capabilities=self._capabilities,
            parameter_overrides=self._parameter_overrides,
            confirm_changeset=self.confirm_changeset,
        )

        if self.save_to_config:
            guided_config.save_config(
                self._parameter_overrides,
                stack_name=self.guided_stack_name,
                s3_bucket=self.guided_s3_bucket,
                s3_prefix=self.guided_s3_prefix,
                region=self.guided_region,
                profile=self.guided_profile,
                confirm_changeset=self.confirm_changeset,
                capabilities=self._capabilities,
            )
