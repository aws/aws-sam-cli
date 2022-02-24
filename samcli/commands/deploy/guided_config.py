"""
Set of Utilities to deal with reading/writing to configuration file during sam deploy
"""
from typing import Any

import click

from samcli.cli.context import get_cmd_names
from samcli.commands.deploy.exceptions import GuidedDeployFailedError
from samcli.lib.config.samconfig import SamConfig, DEFAULT_ENV, DEFAULT_CONFIG_FILE_NAME


class GuidedConfig:
    def __init__(self, template_file, section):
        self.template_file = template_file
        self.section = section

    def get_config_ctx(self, config_file=None):
        ctx = click.get_current_context()

        samconfig_dir = getattr(ctx, "samconfig_dir", None)
        samconfig = SamConfig(
            config_dir=samconfig_dir if samconfig_dir else SamConfig.config_dir(template_file_path=self.template_file),
            filename=config_file or DEFAULT_CONFIG_FILE_NAME,
        )
        return ctx, samconfig

    def read_config_showcase(self, config_file=None):
        _, samconfig = self.get_config_ctx(config_file)

        status = "Found" if samconfig.exists() else "Not found"
        msg = (
            "Syntax invalid in samconfig.toml; save values "
            "through sam deploy --guided to overwrite file with a valid set of values."
        )
        config_sanity = samconfig.sanity_check()
        click.secho("\nConfiguring SAM deploy\n======================", fg="yellow")
        click.echo(f"\n\tLooking for config file [{config_file}] :  {status}")
        if samconfig.exists():
            click.echo("\tReading default arguments  :  {}".format("Success" if config_sanity else "Failure"))

        if not config_sanity and samconfig.exists():
            raise GuidedDeployFailedError(msg)

    def save_config(
        self,
        parameter_overrides,
        config_env=DEFAULT_ENV,
        config_file=None,
        signing_profiles=None,
        image_repositories=None,
        **kwargs,
    ):

        ctx, samconfig = self.get_config_ctx(config_file)

        cmd_names = get_cmd_names(ctx.info_name, ctx)

        for key, value in kwargs.items():
            if isinstance(value, (list, tuple)):
                value = " ".join(val for val in value)
            if value:
                samconfig.put(cmd_names, self.section, key, value, env=config_env)

        self._save_parameter_overrides(cmd_names, config_env, parameter_overrides, samconfig)
        self._save_image_repositories(cmd_names, config_env, samconfig, image_repositories)
        self._save_signing_profiles(cmd_names, config_env, samconfig, signing_profiles)

        samconfig.flush()

        click.echo("\n\tSaved arguments to config file")
        click.echo("\tRunning 'sam deploy' for future deployments will use the parameters saved above.")
        click.echo("\tThe above parameters can be changed by modifying samconfig.toml")
        click.echo(
            "\tLearn more about samconfig.toml syntax at "
            "\n\thttps://docs.aws.amazon.com/serverless-application-model/latest/"
            "developerguide/serverless-sam-cli-config.html\n"
        )

    def _save_signing_profiles(self, cmd_names, config_env, samconfig, signing_profiles):
        if signing_profiles:
            _params = []
            for key, value in signing_profiles.items():
                if value.get("profile_owner", None):
                    signing_profile_with_owner = f"{value['profile_name']}:{value['profile_owner']}"
                    _params.append(f"{key}={self.quote_parameter_values(signing_profile_with_owner)}")
                else:
                    _params.append(f"{key}={self.quote_parameter_values(value['profile_name'])}")
            if _params:
                samconfig.put(cmd_names, self.section, "signing_profiles", " ".join(_params), env=config_env)

    def _save_parameter_overrides(self, cmd_names, config_env, parameter_overrides, samconfig):
        if parameter_overrides:
            _params = []
            for key, value in parameter_overrides.items():
                if isinstance(value, dict):
                    if not value.get("Hidden"):
                        _params.append(f"{key}={self.quote_parameter_values(value.get('Value'))}")
                else:
                    _params.append(f"{key}={self.quote_parameter_values(value)}")
            if _params:
                samconfig.put(cmd_names, self.section, "parameter_overrides", " ".join(_params), env=config_env)

    def _save_image_repositories(self, cmd_names, config_env, samconfig, image_repositories):
        # Check for None only as empty dict should be saved to config
        # This can happen in an edge case where all companion stack repos are deleted and
        # the config needs to be updated.
        if image_repositories is not None:
            _image_repositories = [f"{key}={value}" for key, value in image_repositories.items()]
            samconfig.put(cmd_names, self.section, "image_repositories", _image_repositories, env=config_env)

    @staticmethod
    def quote_parameter_values(parameter_value: Any) -> str:
        return '"{}"'.format(parameter_value.replace('"', r"\""))
