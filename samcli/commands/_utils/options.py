"""
Common CLI options shared by various commands
"""

import os
import logging
from functools import partial

import click
from click.types import FuncParamType

from samcli.commands._utils.template import get_template_data, TemplateNotFoundException
from samcli.cli.types import CfnParameterOverridesType, CfnMetadataType, CfnTags, SigningProfilesOptionType
from samcli.commands._utils.custom_options.option_nargs import OptionNargs
from samcli.commands._utils.template import get_template_artifacts_format

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
            # Default value was used. Value can either be template.yaml or template.yml.
            # Decide based on which file exists .yml is the default, even if it does not exist.
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


def image_repositories_callback(ctx, param, provided_value):
    """
    Create an dictionary of function logical ids to ECR URIs.
    :param ctx: Click Context
    :param param: Param name
    :param provided_value: Value provided by Click, after being processed by ImageRepositoriesType.
    :return: dictionary of function logic ids to ECR URIs.
    """

    image_repositories = {}
    for value in provided_value:
        image_repositories.update(value)

    return image_repositories if image_repositories else None


def artifact_callback(ctx, param, provided_value, artifact):
    """
    Provide an error if there are zip/image artifact based resources,
    and an destination export destination is not specified.
    :param ctx: Click Context
    :param param: Param name
    :param provided_value: Value provided by Click, it would be the value provided by the user.
    :param artifact: artifact format that is to be compared against, eg: zip, image.
    :return: Actual value to be used in the CLI
    """

    # NOTE(sriram-mv): Both params and default_map need to be checked, as the option can be either be
    # passed in directly or through configuration file.
    # If passed in through configuration file, default_map is loaded with those values.
    template_file = (
        ctx.params.get("t", False) or ctx.params.get("template_file", False) or ctx.params.get("template", False)
    )
    resolve_s3 = ctx.params.get("resolve_s3", False) or ctx.default_map.get("resolve_s3", False)

    required = any(
        [
            _template_artifact == artifact
            for _template_artifact in get_template_artifacts_format(template_file=template_file)
        ]
    )
    # NOTE(sriram-mv): Explicit check for param name being s3_bucket
    # If that is the case, check for another option called resolve_s3 to be defined.
    # resolve_s3 option resolves for the s3 bucket automatically.
    if param.name == "s3_bucket" and resolve_s3:
        pass
    elif required and not provided_value and param.name == "s3_bucket":
        raise click.BadOptionUsage(option_name=param.name, ctx=ctx, message=f"Missing option '{param.opts[0]}'")

    return provided_value


def resolve_s3_callback(ctx, param, provided_value, artifact, exc_set, exc_not_set):
    """
    S3 Bucket is only required if there are artifacts that are all zip based.
    :param ctx: Click Context
    :param param: Param name
    :param provided_value: Value provided by Click, it would be the value provided by the user.
    :param artifact: artifact format that is to be compared against, eg: zip, image.
    :param exc_set: Exception to be thrown if both `--resolve-s3` and `--s3-bucket` are set.
    :param exc_not_set: Exception to be thrown if either `--resolve-s3` and `--s3-bucket` are not set
    and are required because the template contains zip based artifacts.
    :return: Actual value to be used in the CLI
    """

    template_file = (
        ctx.params.get("t", False) or ctx.params.get("template_file", False) or ctx.params.get("template", False)
    )

    required = any(
        [
            _template_artifact == artifact
            for _template_artifact in get_template_artifacts_format(template_file=template_file)
        ]
    )
    # NOTE(sriram-mv): Explicit check for s3_bucket being explicitly passed in along with `--resolve-s3`.
    # NOTE(sriram-mv): Both params and default_map need to be checked, as the option can be either be
    # passed in directly or through configuration file.
    # If passed in through configuration file, default_map is loaded with those values.
    s3_bucket_provided = ctx.params.get("s3_bucket", False) or ctx.default_map.get("s3_bucket", False)
    if provided_value and s3_bucket_provided:
        raise exc_set()
    if required and not provided_value and not s3_bucket_provided:
        raise exc_not_set()

    return provided_value


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


def signing_profiles_click_option():
    return click.option(
        "--signing-profiles",
        cls=OptionNargs,
        type=SigningProfilesOptionType(),
        default={},
        help="Optional. A string that contains Code Sign configuration parameters as "
        "FunctionOrLayerNameToSign=SigningProfileName:SigningProfileOwner "
        "Since signing profile owner is optional, it could also be written as "
        "FunctionOrLayerNameToSign=SigningProfileName",
    )


def signing_profiles_option(f):
    return signing_profiles_click_option()(f)


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
    if isinstance(value, str):
        return value.split(" ")
    if isinstance(value, (list, tuple)):
        return value
    raise ValueError()


_space_separated_list_func_type.__name__ = "LIST"
