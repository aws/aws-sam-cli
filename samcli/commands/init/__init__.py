# -*- coding: utf-8 -*-
"""
Init command to scaffold a project app from a template
"""
import itertools
import json
import logging
import os
import subprocess

import click

from samcli.cli.main import pass_context, common_options, global_cfg
from samcli.commands.exceptions import UserException
from samcli.local.common.runtime_template import RUNTIMES, SUPPORTED_DEP_MANAGERS
from samcli.lib.telemetry.metrics import track_command
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates
from samcli.commands.init.interactive_init_flow import do_interactive

LOG = logging.getLogger(__name__)


@click.command(
    "init", short_help="Init an AWS SAM application.", context_settings=dict(help_option_names=[u"-h", u"--help"])
)
@click.option(
    "--no-interactive",
    is_flag=True,
    default=False,
    help="Disable interactive prompting for values, and fail if any required values are missing.",
)
@click.option("-l", "--location", help="Template location (git, mercurial, http(s), zip, path)")
@click.option("-r", "--runtime", type=click.Choice(RUNTIMES), help="Lambda Runtime of your app")
@click.option(
    "-d",
    "--dependency-manager",
    type=click.Choice(SUPPORTED_DEP_MANAGERS),
    default=None,
    help="Dependency manager of your Lambda runtime",
    required=False,
)
@click.option("-o", "--output-dir", type=click.Path(), help="Where to output the initialized app into")
@click.option("-n", "--name", help="Name of your project to be generated as a folder")
@click.option(
    "--app-template",
    help="Identifier of the managed application template you want to use. If not sure, call 'sam init' without options for an interactive workflow.",
)
@click.option(
    "--no-input",
    is_flag=True,
    default=False,
    help="Disable prompting and accept default values defined template config",
)
@common_options
@pass_context
@track_command
def cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    do_cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, app_template, no_input)  # pragma: no cover


def do_cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, app_template, no_input):
    # check for mutually exclusive parameters
    if location and app_template:
        msg = """
You must not provide both the --location and --app-template parameters.

You can run 'sam init' without any options for an interactive initialization flow, or you can provide one of the following required parameter combinations:
    --name and --runtime and --app-template
    --location
        """
        raise UserException(msg)
    # check for required parameters
    if location or (name and runtime and dependency_manager and app_template):
        # need to turn app_template into a location before we generate
        extra_context = None
        if app_template:
            templates = InitTemplates(no_interactive)
            location = templates.location_from_app_template(runtime, dependency_manager, app_template)
            no_input = True
            extra_context = {"project_name": name, "runtime": runtime}
        if not output_dir:
            output_dir = "." # default - should I lift this to overall options and seed default?
        do_generate(location, runtime, dependency_manager, output_dir, name, no_input, extra_context)
    elif no_interactive:
        error_msg = """
ERROR: Missing required parameters, with --no-interactive set.

Must provide one of the following required parameter combinations:
    --name and --runtime and --dependency-manager and --app-template
    --location

You can also re-run without the --no-interactive flag to be prompted for required values.
        """
        raise UserException(error_msg)
    else:
        # proceed to interactive state machine, which will call do_generate
        do_interactive(location, runtime, dependency_manager, output_dir, name, app_template, no_input)
