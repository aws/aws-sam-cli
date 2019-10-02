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
    "--no-input",
    is_flag=True,
    default=False,
    help="Disable prompting and accept default values defined template config",
)
@common_options
@pass_context
@track_command
def cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, no_input):
    do_cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, no_input)  # pragma: no cover


def do_cli(ctx, no_interactive, location, runtime, dependency_manager, output_dir, name, no_input):
    # check for required parameters
    if name and (runtime or location):
        do_generate(location, runtime, dependency_manager, output_dir, name, no_input, None)
    elif no_interactive:
        # raise error - this message is a slight mess, and hard to read
        error_msg = """
ERROR: Missing required parameters, with --no-interactive set.

Must provide at one of the following required parameter combinations:
    --name and --runtime
    --name and --location

You can also re-run without the --no-interactive flag to be prompted for required values.
        """
        raise UserException(error_msg)
    else:
        # proceed to interactive state machine, which will call do_generate
        do_interactive(location, runtime, dependency_manager, output_dir, name, no_input)
