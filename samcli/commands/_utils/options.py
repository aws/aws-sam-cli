"""
Common CLI options shared by various commands
"""

import os
import logging
from functools import partial

import click
from click.types import FuncParamType

from samcli.commands._utils.template import get_template_data, TemplateNotFoundException
from samcli.cli.types import CfnParameterOverridesType, CfnMetadataType, CfnTags
from samcli.commands._utils.custom_options.option_nargs import OptionNargs

_TEMPLATE_OPTION_DEFAULT_VALUE = "template.[yaml|yml]"
DEFAULT_STACK_NAME = "sam-app"

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

    original_template_path = os.path.abspath(provided_value)

    search_paths = ["template.yaml", "template.yml"]

    if include_build:
        search_paths.insert(0, os.path.join(".aws-sam", "build", "template.yaml"))

    if provided_value == _TEMPLATE_OPTION_DEFAULT_VALUE:
        # "--template" is an alias of "--template-file", however, only the first option name "--template-file" in
        # ctx.default_map is used as default value of provided value. Here we add "--template"'s value as second
        # default value in this option, so that the command line paramerters from config file can load it.
        if ctx and ctx.default_map.get("template", None):
            provided_value = ctx.default_map.get("template")
        else:
            # Default value was used. Value can either be template.yaml or template.yml. Decide based on which file exists
            # .yml is the default, even if it does not exist.
            provided_value = "template.yml"

            for option in search_paths:
                if os.path.exists(option):
                    provided_value = option
                    break
    result = os.path.abspath(provided_value)

    if ctx:
        # sam configuration file should always be relative to the supplied original template and should not to be set
        # to be .aws-sam/build/
        setattr(ctx, "samconfig_dir", os.path.dirname(original_template_path))
        try:
            # FIX-ME: figure out a way to insert this directly to sam-cli context and not use click context.
            template_data = get_template_data(result)
            setattr(ctx, "template_dict", template_data)
        except TemplateNotFoundException:
            # Ignoring because there are certain cases where template file will not be available, eg: --help
            pass

    LOG.debug("Using SAM Template at %s", result)
    return result


def guided_deploy_stack_name(ctx, param, provided_value):
    """
    Provide a default value for stack name if invoked with a guided deploy.
    :param ctx: Click Context
    :param param: Param name
    :param provided_value: Value provided by Click, it would be the value provided by the user.
    :return: Actual value to be used in the CLI
    """

    guided = ctx.params.get("guided", False) or ctx.params.get("g", False)

    if not guided and not provided_value:
        raise click.BadOptionUsage(
            option_name=param.name,
            ctx=ctx,
            message="Missing option '--stack-name', 'sam deploy --guided' can "
            "be used to provide and save needed parameters for future deploys.",
        )

    return provided_value if provided_value else DEFAULT_STACK_NAME


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
    return click.option(
        "--template-file",
        "--template",
        "-t",
        default=_TEMPLATE_OPTION_DEFAULT_VALUE,
        type=click.Path(),
        envvar="SAM_TEMPLATE_FILE",
        callback=partial(get_or_default_template_file_name, include_build=include_build),
        show_default=True,
        is_eager=True,
        help="AWS SAM template which references built artifacts for resources in the template. (if applicable)"
        if include_build
        else "AWS SAM template file.",
    )


def docker_common_options(f):
    for option in reversed(docker_click_options()):
        option(f)

    return f


def docker_click_options():
    return [
        click.option(
            "--skip-pull-image",
            is_flag=True,
            help="Specify whether CLI should skip pulling down the latest Docker image for Lambda runtime.",
            envvar="SAM_SKIP_PULL_IMAGE",
            default=False,
        ),
        click.option(
            "--docker-network",
            envvar="SAM_DOCKER_NETWORK",
            help="Specifies the name or id of an existing docker network to lambda docker "
            "containers should connect to, along with the default bridge network. If not specified, "
            "the Lambda containers will only connect to the default bridge docker network.",
        ),
    ]


def parameter_override_click_option():
    return click.option(
        "--parameter-overrides",
        cls=OptionNargs,
        type=CfnParameterOverridesType(),
        default={},
        help="Optional. A string that contains AWS CloudFormation parameter overrides encoded as key=value pairs."
        "For example, 'ParameterKey=KeyPairName,ParameterValue=MyKey ParameterKey=InstanceType,"
        "ParameterValue=t1.micro' or KeyPairName=MyKey InstanceType=t1.micro",
    )


def parameter_override_option(f):
    return parameter_override_click_option()(f)


def no_progressbar_click_option():
    return click.option(
        "--no-progressbar",
        default=False,
        required=False,
        is_flag=True,
        help="Does not showcase a progress bar when uploading artifacts to s3 ",
    )


def no_progressbar_option(f):
    return no_progressbar_click_option()(f)


def metadata_click_option():
    return click.option(
        "--metadata",
        type=CfnMetadataType(),
        help="Optional. A map of metadata to attach to ALL the artifacts that are referenced in your template.",
    )


def metadata_override_option(f):
    return metadata_click_option()(f)


def capabilities_click_option():
    return click.option(
        "--capabilities",
        cls=OptionNargs,
        required=False,
        type=FuncParamType(func=_space_separated_list_func_type),
        help="A list of  capabilities  that  you  must  specify"
        "before  AWS  Cloudformation  can create certain stacks. Some stack tem-"
        "plates might include resources that can affect permissions in your  AWS"
        "account,  for  example, by creating new AWS Identity and Access Manage-"
        "ment (IAM) users. For those stacks,  you  must  explicitly  acknowledge"
        "their  capabilities by specifying this parameter. The only valid values"
        "are CAPABILITY_IAM and CAPABILITY_NAMED_IAM. If you have IAM resources,"
        "you  can specify either capability. If you have IAM resources with cus-"
        "tom names, you must specify CAPABILITY_NAMED_IAM. If you don't  specify"
        "this  parameter, this action returns an InsufficientCapabilities error.",
    )


def capabilities_override_option(f):
    return capabilities_click_option()(f)


def tags_click_option():
    return click.option(
        "--tags",
        cls=OptionNargs,
        type=CfnTags(),
        required=False,
        help="A list of tags to associate with the stack that is created or updated."
        "AWS CloudFormation also propagates these tags to resources "
        "in the stack if the resource supports it.",
    )


def tags_override_option(f):
    return tags_click_option()(f)


def notification_arns_click_option():
    return click.option(
        "--notification-arns",
        cls=OptionNargs,
        type=FuncParamType(func=_space_separated_list_func_type),
        required=False,
        help="Amazon  Simple  Notification  Service  topic"
        "Amazon  Resource  Names  (ARNs) that AWS CloudFormation associates with"
        "the stack.",
    )


def notification_arns_override_option(f):
    return notification_arns_click_option()(f)


def _space_separated_list_func_type(value):
    return value.split(" ") if not isinstance(value, tuple) else value


_space_separated_list_func_type.__name__ = "LIST"
