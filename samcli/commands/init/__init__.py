# -*- coding: utf-8 -*-
"""
Init command to scaffold a project app from a template
"""
import logging
import click

from samcli.cli.main import pass_context, common_options
from samcli.local.init import generate_project
from samcli.local.init import RUNTIME_TEMPLATE_MAPPING
from samcli.local.init.exceptions import GenerateProjectFailedError
from samcli.commands.exceptions import UserException

LOG = logging.getLogger(__name__)
SUPPORTED_RUNTIME = [r for r in RUNTIME_TEMPLATE_MAPPING]


@click.command(context_settings=dict(help_option_names=[u'-h', u'--help']))
@click.option('-l', '--location', help="Template location (git, mercurial, http(s), zip, path)")
@click.option('-r', '--runtime', type=click.Choice(SUPPORTED_RUNTIME), default="nodejs8.10",
              help="Lambda Runtime of your app")
@click.option('-o', '--output-dir', default='.', type=click.Path(), help="Where to output the initialized app into")
@click.option('-n', '--name', default="sam-app", help="Name of your project to be generated as a folder")
@click.option('--no-input', is_flag=True, default=False,
              help="Disable prompting and accept default values defined template config")
@common_options
@pass_context
def cli(ctx, location, runtime, output_dir, name, no_input):
    """ \b
        Initialize a serverless application with a SAM template, folder
        structure for your Lambda functions, connected to an event source such as APIs,
        S3 Buckets or DynamoDB Tables. This application includes everything you need to
        get started with serverless and eventually grow into a production scale application.
        \b
        This command can initialize a boilerplate serverless app. If you want to create your own
        template as well as use a custom location please take a look at our official documentation.

    \b
    Common usage:

        \b
        Initializes a new SAM project using Python 3.6 default template runtime
        \b
        $ sam init --runtime python3.6
        \b
        Initializes a new SAM project using custom template in a Git/Mercurial repository
        \b
        # gh being expanded to github url
        $ sam init --location gh:aws-samples/cookiecutter-aws-sam-python
        \b
        $ sam init --location git+ssh://git@github.com/aws-samples/cookiecutter-aws-sam-python.git
        \b
        $ sam init --location hg+ssh://hg@bitbucket.org/repo/template-name

        \b
        Initializes a new SAM project using custom template in a Zipfile
        \b
        $ sam init --location /path/to/template.zip
        \b
        $ sam init --location https://example.com/path/to/template.zip

        \b
        Initializes a new SAM project using custom template in a local path
        \b
        $ sam init --location /path/to/template/folder

    """
    # All logic must be implemented in the `do_cli` method. This helps ease unit tests
    do_cli(ctx, location, runtime, output_dir,
           name, no_input)  # pragma: no cover


def do_cli(ctx, location, runtime, output_dir, name, no_input):
    """
    Implementation of the ``cli`` method, just separated out for unit testing purposes
    """
    LOG.debug("Init command")
    click.secho("[+] Initializing project structure...", fg="green")

    try:
        generate_project(location, runtime, output_dir, name, no_input)
        # Custom templates can implement their own visual cues so let's not repeat the message
        if not location:
            click.secho(
                "[SUCCESS] - Read {name}/README.md for further instructions on how to proceed"
                .format(name=name), bold=True)
        click.secho("[*] Project initialization is now complete", fg="green")
    except GenerateProjectFailedError as e:
        raise UserException(str(e))
