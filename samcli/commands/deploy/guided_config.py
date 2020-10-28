"""
Set of Utilities to deal with reading/writing to configuration file during sam deploy
"""

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

    def save_config(self, parameter_overrides, config_env=DEFAULT_ENV, config_file=None, **kwargs):

        ctx, samconfig = self.get_config_ctx(config_file)

        cmd_names = get_cmd_names(ctx.info_name, ctx)

        for key, value in kwargs.items():
            if isinstance(value, (list, tuple)):
                value = " ".join(val for val in value)
            if value:
                samconfig.put(cmd_names, self.section, key, value, env=config_env)

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

        samconfig.flush()

        click.echo("\n\tSaved arguments to config file")
        click.echo("\tRunning 'sam deploy' for future deployments will use the parameters saved above.")
        click.echo("\tThe above parameters can be changed by modifying samconfig.toml")
        click.echo(
            "\tLearn more about samconfig.toml syntax at "
            "\n\thttps://docs.aws.amazon.com/serverless-application-model/latest/"
            "developerguide/serverless-sam-cli-config.html"
        )

    def quote_parameter_values(self, parameter_value):
        return '"{}"'.format(parameter_value)
