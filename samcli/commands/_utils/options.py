"""
Common CLI options shared by various commands
"""

import os
import logging
from functools import partial

import click
from samcli.cli.types import CfnParameterOverridesType

_TEMPLATE_OPTION_DEFAULT_VALUE = "template.[yaml|yml]"


LOG = logging.getLogger(__name__)


def get_or_default_template_file_name(ctx, param, provided_value, include_build):
    """
    Default value for the template file name option is more complex than what Click can handle.
    This method either returns user provided file name or one of the two default options (template.yaml/template.yml)
    depending on the file that exists

    :param ctx: Click Context
    :param param: Param name
    :param provided_value: Value provided by Click. It could either be the default value or provided by user.
    :return: Actual value to be used in the CLI
    """

    search_paths = [
        "template.yaml",
        "template.yml",
    ]

    if include_build:
        search_paths.insert(0, os.path.join(".aws-sam", "build", "template.yaml"))

    if provided_value == _TEMPLATE_OPTION_DEFAULT_VALUE:
        # Default value was used. Value can either be template.yaml or template.yml. Decide based on which file exists
        # .yml is the default, even if it does not exist.
        provided_value = "template.yml"

        for option in search_paths:
            if os.path.exists(option):
                provided_value = option
                break

    result = os.path.abspath(provided_value)
    LOG.debug("Using SAM Template at %s", result)
    return result


def template_common_option(f):
    """
    Common ClI option for template

    :param f: Callback passed by Click
    :return: Callback
    """
    return template_click_option()(f)


def template_option_without_build(f):
    """
    Common ClI option for template

    :param f: Callback passed by Click
    :return: Callback
    """
    return template_click_option(include_build=False)(f)


def template_click_option(include_build=True):
    """
    Click Option for template option
    """
    return click.option('--template', '-t',
                        default=_TEMPLATE_OPTION_DEFAULT_VALUE,
                        type=click.Path(),
                        envvar="SAM_TEMPLATE_FILE",
                        callback=partial(get_or_default_template_file_name, include_build=include_build),
                        show_default=True,
                        help="AWS SAM template file")


def docker_common_options(f):
    for option in reversed(docker_click_options()):
        option(f)

    return f


def docker_click_options():

    return [
        click.option('--skip-pull-image',
                     is_flag=True,
                     help="Specify whether CLI should skip pulling down the latest Docker image for Lambda runtime.",
                     envvar="SAM_SKIP_PULL_IMAGE",
                     default=False),

        click.option('--docker-network',
                     envvar="SAM_DOCKER_NETWORK",
                     help="Specifies the name or id of an existing docker network to lambda docker "
                          "containers should connect to, along with the default bridge network. If not specified, "
                          "the Lambda containers will only connect to the default bridge docker network."),
    ]


def parameter_override_click_option():
    return click.option("--parameter-overrides",
                        type=CfnParameterOverridesType(),
                        help="Optional. A string that contains CloudFormation parameter overrides encoded as key=value "
                             "pairs. Use the same format as the AWS CLI, e.g. 'ParameterKey=KeyPairName,"
                             "ParameterValue=MyKey ParameterKey=InstanceType,ParameterValue=t1.micro'")


def parameter_override_option(f):
    return parameter_override_click_option()(f)
