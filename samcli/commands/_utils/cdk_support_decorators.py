"""CDK Support"""
import logging

import click

from samcli.cli.context import Context
from samcli.lib.iac.cdk.utils import is_cdk_project

LOG = logging.getLogger(__name__)


def unsupported_command_cdk(alternative_command=None):
    """
    Log a warning message to the user if they attempt
    to use a CDK template with an unsupported sam command

    Parameters
    ----------
    alternative_command:
        Alternative command to use instead of sam command

    """

    def decorator(func):
        def wrapped(*args, **kwargs):
            ctx = Context.get_current_context()

            try:
                template_dict = ctx.template_dict
            except AttributeError:
                LOG.debug("Ignoring CDK project check as template is not provided in context.")
                return func(*args, **kwargs)

            if is_cdk_project(template_dict):
                click.secho("Warning: CDK apps are not officially supported with this command.", fg="yellow")
                if alternative_command:
                    click.secho(f"We recommend you use this alternative command: {alternative_command}", fg="yellow")

            return func(*args, **kwargs)

        return wrapped

    return decorator
