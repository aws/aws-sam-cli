"""
Common CLI options shared by various commands
"""

import os
import logging
from functools import partial

import click
from click.types import FuncParamType

from samcli.commands._utils.constants import (
    DEFAULT_STACK_NAME,
    DEFAULT_BUILD_DIR,
    DEFAULT_CACHE_DIR,
    DEFAULT_BUILT_TEMPLATE_PATH,
)
from samcli.commands._utils.custom_options.hook_name_option import HookNameOption
from samcli.commands._utils.parameterized_option import parameterized_option
from samcli.commands._utils.template import get_template_data, TemplateNotFoundException
from samcli.cli.types import (
    CfnParameterOverridesType,
    CfnMetadataType,
    CfnTags,
    SigningProfilesOptionType,
    ImageRepositoryType,
    ImageRepositoriesType,
)
from samcli.commands._utils.custom_options.option_nargs import OptionNargs
from samcli.commands._utils.template import get_template_artifacts_format
from samcli.lib.hook.hook_wrapper import get_available_hook_packages_ids
from samcli.lib.observability.util import OutputOption
from samcli.lib.utils.packagetype import ZIP, IMAGE

_TEMPLATE_OPTION_DEFAULT_VALUE = "template.[yaml|yml|json]"

LOG = logging.getLogger(__name__)


def get_or_default_template_file_name(ctx, param, provided_value, include_build):
    """
    Default value for the template file name option is more complex than what Click can handle.
    This method either returns user provided file name or one of the two default options (template.yaml/template.yml)
    depending on the file that exists

    :param ctx: Click Context
    :param param: Param name
    :param provided_value: Value provided by Click. It could either be the default value or provided by user.
    :param include_build: A boolean to set whether to search build template or not.
    :return: Actual value to be used in the CLI
    """

    original_template_path = os.path.abspath(provided_value)

    search_paths = ["template.yaml", "template.yml", "template.json"]

    if include_build:
        search_paths.insert(0, DEFAULT_BUILT_TEMPLATE_PATH)

    if provided_value == _TEMPLATE_OPTION_DEFAULT_VALUE:
        # "--template" is an alias of "--template-file", however, only the first option name "--template-file" in
        # ctx.default_map is used as default value of provided value. Here we add "--template"'s value as second
        # default value in this option, so that the command line parameters from config file can load it.
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


def skip_prepare_infra_callback(ctx, param, provided_value):
    """
    Callback for --skip-prepare-infra to check if --hook-name is also specified

    Parameters
    ----------
    ctx: click.core.Context
        Click context
    param: click.Option
        Parameter properties
    provided_value: bool
        True if option was provided
    """
    is_option_provided = provided_value or ctx.default_map.get("skip_prepare_infra")
    is_hook_provided = ctx.params.get("hook_name") or ctx.default_map.get("hook_name")

    if is_option_provided and not is_hook_provided:
        raise click.BadOptionUsage(option_name=param.name, ctx=ctx, message="Missing option --hook-name")


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


def common_observability_click_options():
    return [
        click.option(
            "--start-time",
            "-s",
            default="10m ago",
            help="Fetch events starting at this time. Time can be relative values like '5mins ago', 'yesterday' or "
            "formatted timestamp like '2018-01-01 10:10:10'. Defaults to '10mins ago'.",
        ),
        click.option(
            "--end-time",
            "-e",
            default=None,
            help="Fetch events up to this time. Time can be relative values like '5mins ago', 'tomorrow' or "
            "formatted timestamp like '2018-01-01 10:10:10'",
        ),
        click.option(
            "--tail",
            "-t",
            is_flag=True,
            help="Tail events. This will ignore the end time argument and continue to fetch events as they "
            "become available. If option --tail without a --name will pull from all possible resources",
        ),
        click.option(
            "--output",
            help="""
            The formatting style of the command output. Following options are available:\n
            TEXT: Prints information as regular text with some formatting (default option)\n
            JSON: Prints each line as JSON without formatting
            """,
            type=click.Choice(OutputOption.__members__, case_sensitive=False),
        ),
    ]


def common_observability_options(f):
    for option in common_observability_click_options():
        option(f)

    return f


def metadata_click_option():
    return click.option(
        "--metadata",
        type=CfnMetadataType(),
        help="Optional. A map of metadata to attach to ALL the artifacts that are referenced in your template.",
    )


def metadata_option(f):
    return metadata_click_option()(f)


def capabilities_click_option(default):
    return click.option(
        "--capabilities",
        cls=OptionNargs,
        required=False,
        default=default,
        type=FuncParamType(func=_space_separated_list_func_type),
        help="A list of capabilities that you must specify "
        "before AWS Cloudformation can create certain stacks. Some stack templates "
        "might include resources that can affect permissions in your AWS "
        "account, for example, by creating new AWS Identity and Access Management "
        "(IAM) users. For those stacks, you must explicitly acknowledge "
        "their capabilities by specifying this parameter. The only valid values"
        "are CAPABILITY_IAM and CAPABILITY_NAMED_IAM. If you have IAM resources, "
        "you can specify either capability. If you have IAM resources with custom "
        "names, you must specify CAPABILITY_NAMED_IAM. If you don't specify "
        "this parameter, this action returns an InsufficientCapabilities error.",
    )


@parameterized_option
def capabilities_option(f, default=None):
    return capabilities_click_option(default)(f)


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


def tags_option(f):
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


def notification_arns_option(f):
    return notification_arns_click_option()(f)


def stack_name_click_option(required, callback):
    return click.option(
        "--stack-name",
        required=required,
        callback=callback,
        help="The name of the AWS CloudFormation stack you're deploying to. "
        "If you specify an existing stack, the command updates the stack. "
        "If you specify a new stack, the command creates it.",
    )


@parameterized_option
def stack_name_option(f, required=False, callback=None):
    return stack_name_click_option(required, callback)(f)


def s3_bucket_click_option(disable_callback):
    callback = None if disable_callback else partial(artifact_callback, artifact=ZIP)

    return click.option(
        "--s3-bucket",
        required=False,
        help="The name of the S3 bucket where this command uploads the artifacts that are referenced in your template.",
        callback=callback,
    )


@parameterized_option
def s3_bucket_option(f, disable_callback=False):
    return s3_bucket_click_option(disable_callback)(f)


def build_dir_click_option():
    return click.option(
        "--build-dir",
        "-b",
        default=DEFAULT_BUILD_DIR,
        type=click.Path(file_okay=False, dir_okay=True, writable=True),  # Must be a directory
        help="Path to a folder where the built artifacts will be stored. "
        "This directory will be first removed before starting a build.",
    )


def build_dir_option(f):
    return build_dir_click_option()(f)


def cache_dir_click_option():
    return click.option(
        "--cache-dir",
        "-cd",
        default=DEFAULT_CACHE_DIR,
        type=click.Path(file_okay=False, dir_okay=True, writable=True),  # Must be a directory
        help="The folder where the cache artifacts will be stored when --cached is specified. "
        "The default cache directory is .aws-sam/cache",
    )


def cache_dir_option(f):
    return cache_dir_click_option()(f)


def base_dir_click_option():
    return click.option(
        "--base-dir",
        "-s",
        default=None,
        type=click.Path(dir_okay=True, file_okay=False),  # Must be a directory
        help="Resolve relative paths to function's source code with respect to this folder. Use this if "
        "SAM template and your source code are not in same enclosing folder. By default, relative paths "
        "are resolved with respect to the SAM template's location",
    )


def base_dir_option(f):
    return base_dir_click_option()(f)


def manifest_click_option():
    return click.option(
        "--manifest",
        "-m",
        default=None,
        type=click.Path(),
        help="Path to a custom dependency manifest (e.g., package.json) to use instead of the default one",
    )


def manifest_option(f):
    return manifest_click_option()(f)


def cached_click_option():
    return click.option(
        "--cached/--no-cached",
        "-c",
        default=False,
        required=False,
        is_flag=True,
        help="Enable cached builds. Use this flag to reuse build artifacts that have not changed from previous builds. "
        "AWS SAM evaluates whether you have made any changes to files in your project directory. \n\n"
        "Note: AWS SAM does not evaluate whether changes have been made to third party modules "
        "that your project depends on, where you have not provided a specific version. "
        "For example, if your Python function includes a requirements.txt file with the following entry "
        "requests=1.x and the latest request module version changes from 1.1 to 1.2, "
        "SAM will not pull the latest version until you run a non-cached build.",
    )


def cached_option(f):
    return cached_click_option()(f)


def image_repository_click_option():
    return click.option(
        "--image-repository",
        callback=partial(artifact_callback, artifact=IMAGE),
        type=ImageRepositoryType(),
        required=False,
        help="ECR repo uri where this command uploads the image artifacts that are referenced in your template.",
    )


def image_repository_option(f):
    return image_repository_click_option()(f)


def image_repositories_click_option():
    return click.option(
        "--image-repositories",
        multiple=True,
        callback=image_repositories_callback,
        type=ImageRepositoriesType(),
        required=False,
        help="Specify mapping of Function Logical ID to ECR Repo uri, of the form Function_Logical_ID=ECR_Repo_Uri."
        "This option can be specified multiple times.",
    )


def image_repositories_option(f):
    return image_repositories_click_option()(f)


def s3_prefix_click_option():
    return click.option(
        "--s3-prefix",
        required=False,
        help="A prefix name that the command adds to the artifacts "
        "name when it uploads them to the S3 bucket. The prefix name is a "
        "path name (folder name) for the S3 bucket.",
    )


def s3_prefix_option(f):
    return s3_prefix_click_option()(f)


def kms_key_id_click_option():
    return click.option(
        "--kms-key-id",
        required=False,
        help="The ID of an AWS KMS key that the command uses to encrypt artifacts that are at rest in the S3 bucket.",
    )


def kms_key_id_option(f):
    return kms_key_id_click_option()(f)


def use_json_click_option():
    return click.option(
        "--use-json",
        required=False,
        is_flag=True,
        help="Indicates whether to use JSON as the format for "
        "the output AWS CloudFormation template. YAML is used by default.",
    )


def use_json_option(f):
    return use_json_click_option()(f)


def force_upload_click_option():
    return click.option(
        "--force-upload",
        required=False,
        is_flag=True,
        help="Indicates whether to override existing files "
        "in the S3 bucket. Specify this flag to upload artifacts even if they "
        "match existing artifacts in the S3 bucket.",
    )


def force_upload_option(f):
    return force_upload_click_option()(f)


def resolve_s3_click_option(guided):
    from samcli.commands.package.exceptions import PackageResolveS3AndS3SetError, PackageResolveS3AndS3NotSetError

    callback = (
        None
        if guided
        else partial(
            resolve_s3_callback,
            artifact=ZIP,
            exc_set=PackageResolveS3AndS3SetError,
            exc_not_set=PackageResolveS3AndS3NotSetError,
        )
    )
    return click.option(
        "--resolve-s3",
        required=False,
        is_flag=True,
        callback=callback,
        help="Automatically resolve s3 bucket for non-guided deployments. "
        "Enabling this option will also create a managed default s3 bucket for you. "
        "If you do not provide a --s3-bucket value, the managed bucket will be used. "
        "Do not use --guided with this option.",
    )


def hook_name_click_option(force_prepare=True, invalid_coexist_options=None):
    """
    Click Option for hook-name option
    """

    def hook_name_setup(f):
        return click.option(
            "--hook-name",
            default=None,
            type=click.STRING,
            required=False,
            help=f"The id of the hook package to be used to extend the SAM CLI commands functionality. As an example, "
            f"you can use `terraform` to extend SAM CLI commands functionality to support terraform applications. "
            f"Available Hook Names {get_available_hook_packages_ids()}",
        )(f)

    def hook_name_processer_wrapper(f):
        configuration_setup_params = ()
        configuration_setup_attrs = {}
        configuration_setup_attrs[
            "help"
        ] = "This is a hidden click option whose callback function to run the provided hook package."
        configuration_setup_attrs["is_eager"] = True
        configuration_setup_attrs["expose_value"] = False
        configuration_setup_attrs["hidden"] = True
        configuration_setup_attrs["type"] = click.STRING
        configuration_setup_attrs["cls"] = HookNameOption
        configuration_setup_attrs["force_prepare"] = force_prepare
        configuration_setup_attrs["invalid_coexist_options"] = (
            invalid_coexist_options if invalid_coexist_options else []
        )
        return click.option(*configuration_setup_params, **configuration_setup_attrs)(f)

    def composed_decorator(decorators):
        def decorator(f):
            for deco in decorators:
                f = deco(f)
            return f

        return decorator

    # Compose decorators here to make sure the context parameters are updated before callback function
    decorator_list = [hook_name_setup, hook_name_processer_wrapper]
    return composed_decorator(decorator_list)


def skip_prepare_infra_click_option():
    """
    Click option to skip the hook preparation stage
    """
    return click.option(
        "--skip-prepare-infra",
        is_flag=True,
        required=False,
        callback=skip_prepare_infra_callback,
        help="Use this option to skip the preparation stage if there have not been any infrastructure changes. "
        "The --hook-name option should also be specified when skipping infrastructure preparation.",
    )


def skip_prepare_infra_option(f):
    return skip_prepare_infra_click_option()(f)


@parameterized_option
def resolve_s3_option(f, guided=False):
    return resolve_s3_click_option(guided)(f)


def role_arn_click_option():
    return click.option(
        "--role-arn",
        required=False,
        help="The Amazon Resource Name (ARN) of an AWS Identity "
        "and Access Management (IAM) role that AWS CloudFormation assumes when "
        "executing the change set.",
    )


def role_arn_option(f):
    return role_arn_click_option()(f)


def resolve_image_repos_click_option():
    return click.option(
        "--resolve-image-repos",
        required=False,
        is_flag=True,
        help="Automatically create and delete ECR repositories for image-based functions in non-guided deployments. "
        "A companion stack containing ECR repos for each function will be deployed along with the template stack. "
        "Automatically created image repositories will be deleted if the corresponding functions are removed.",
    )


def resolve_image_repos_option(f):
    return resolve_image_repos_click_option()(f)


def use_container_build_click_option():
    return click.option(
        "--use-container",
        "-u",
        is_flag=True,
        help="If your functions depend on packages that have natively compiled dependencies, use this flag "
        "to build your function inside an AWS Lambda-like Docker container",
    )


def use_container_build_option(f):
    return use_container_build_click_option()(f)


def _space_separated_list_func_type(value):
    if isinstance(value, str):
        return value.split(" ")
    if isinstance(value, (list, tuple)):
        return value
    raise ValueError()


_space_separated_list_func_type.__name__ = "LIST"
