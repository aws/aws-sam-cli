"""
Init command to scaffold a project app from a template
"""
import json
import logging
from json import JSONDecodeError

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option
from samcli.cli.main import common_options, pass_context, print_cmdline_args
from samcli.commands._utils.click_mutex import ClickMutex
from samcli.commands.init.core.command import InitCommand
from samcli.commands.init.init_flow_helpers import _get_runtime_from_image, get_architectures, get_sorted_runtimes
from samcli.lib.build.constants import DEPRECATED_RUNTIMES
from samcli.lib.telemetry.metric import track_command
from samcli.lib.utils.architecture import ARM64, X86_64
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.version_checker import check_newer_version
from samcli.local.common.runtime_template import INIT_RUNTIMES, LAMBDA_IMAGES_RUNTIMES, SUPPORTED_DEP_MANAGERS

LOG = logging.getLogger(__name__)

HELP_TEXT = "Initialize an AWS SAM application."

DESCRIPTION = """ \b
  Initialize a serverless application with an AWS SAM template, source code and 
  structure for serverless abstractions which connect to event source(s) such as APIs,
  S3 Buckets or DynamoDB Tables. This application includes everything one needs to
  get started with serverless and eventually grow into a production scale application.
  \b
  To explore initializing with your own template and/or using a custom location, 
  please take a look at our official documentation.
"""

INCOMPATIBLE_PARAMS_HINT = """You can run 'sam init' without any options for an interactive initialization flow, \
or you can provide one of the following required parameter combinations:
\t--name, --location, or
\t--name, --package-type, --base-image, or
\t--name, --runtime, --app-template, --dependency-manager
"""

REQUIRED_PARAMS_HINT = "You can also re-run without the --no-interactive flag to be prompted for required values."

INIT_INTERACTIVE_OPTION_GUIDE = """
You can preselect a particular runtime or package type when using the `sam init` experience.
Call `sam init --help` to learn more.
"""


class PackageType:
    """
    This class has a callback function for the --package-type parameter to handle default value
    and also store if the --package-type param was passed explicitly
    """

    explicit = False

    def __init__(self):
        pass

    @staticmethod
    def pt_callback(ctx, param, provided_value):
        """
        This function is the callback for the --package-type param. Here we check if --package-type was passed or not.
        If not, we use the default value of --package-type to be Zip.
        """
        if provided_value is None:
            return ZIP
        PackageType.explicit = True
        return provided_value


def non_interactive_validation(func):
    """
    Check requirement for --dependency-manager parameter for non interactive mode

    --dependency-manager parameter is only required if --package-type is ZIP
    or --base-image is one of the java ones
    """

    def wrapped(*args, **kwargs):
        ctx = click.get_current_context()
        non_interactive = ctx.params.get("no_interactive")

        # only run in non interactive mode
        if non_interactive:
            package_type = ctx.params.get("package_type")
            base_image = ctx.params.get("base_image")
            dependency_manager = ctx.params.get("dependency_manager")
            location = ctx.params.get("location")

            # TODO: improve how we check for java type images instead of searching for substring
            java_base_image = base_image and "java" in base_image

            # dependency manager is only required for ZIP types if location is not also specified
            # and is required for java IMAGE packages
            if not location and (package_type == ZIP or java_base_image):
                if not dependency_manager:
                    raise click.UsageError("Missing parameter --dependency-manager")

        return func(*args, **kwargs)

    return wrapped


@click.command(
    "init",
    short_help=HELP_TEXT,
    context_settings={"max_content_width": 120},
    cls=InitCommand,
    description=DESCRIPTION,
    requires_credentials=False,
)
@configuration_option(provider=ConfigProvider(section="parameters"))
@click.option(
    "--no-interactive",
    is_flag=True,
    default=False,
    help="Disable interactive prompting for init parameters. (fail if any required values are missing)",
    cls=ClickMutex,
    required_param_lists=[
        ["name", "location"],
        ["name", "package_type", "base_image"],
        ["name", "runtime", "dependency_manager", "app_template"],
        # check non_interactive_validation for additional validations
    ],
    required_params_hint=REQUIRED_PARAMS_HINT,
)
@click.option(
    "-a",
    "--architecture",
    type=click.Choice([ARM64, X86_64]),
    replace_help_option="--architecture ARCHITECTURE",
    help="Architectures for Lambda functions." + click.style(f"\n\nArchitectures: {[ARM64, X86_64]}", bold=True),
    cls=ClickMutex,
)
@click.option(
    "-l",
    "--location",
    help="Template location (git, mercurial, http(s), zip, path).",
    cls=ClickMutex,
    incompatible_params=["package_type", "runtime", "base_image", "dependency_manager", "app_template"],
    incompatible_params_hint=INCOMPATIBLE_PARAMS_HINT,
)
@click.option(
    "-r",
    "--runtime",
    type=click.Choice(get_sorted_runtimes(INIT_RUNTIMES)),
    replace_help_option="--runtime RUNTIME",
    help="Lambda runtime for application."
    + click.style(f"\n\nRuntimes: {', '.join(get_sorted_runtimes(INIT_RUNTIMES))}", bold=True),
    cls=ClickMutex,
    incompatible_params=["location", "base_image"],
    incompatible_params_hint=INCOMPATIBLE_PARAMS_HINT,
)
@click.option(
    "-p",
    "--package-type",
    type=click.Choice([ZIP, IMAGE]),
    help="Lambda deployment package type." + click.style(f"\n\nPackage Types: {', '.join([ZIP, IMAGE])}", bold=True),
    replace_help_option="--package-type PACKAGE_TYPE",
    cls=ClickMutex,
    callback=PackageType.pt_callback,
    incompatible_params=["location"],
    incompatible_params_hint=INCOMPATIBLE_PARAMS_HINT,
)
@click.option(
    "-i",
    "--base-image",
    type=click.Choice(LAMBDA_IMAGES_RUNTIMES),
    default=None,
    help="Lambda base image for deploying IMAGE based package type."
    + click.style(f"\n\nBase images: {', '.join(LAMBDA_IMAGES_RUNTIMES)}", bold=True),
    replace_help_option="--base-image BASE_IMAGE",
    cls=ClickMutex,
    incompatible_params=["location", "runtime"],
    incompatible_params_hint=INCOMPATIBLE_PARAMS_HINT,
)
@click.option(
    "-d",
    "--dependency-manager",
    type=click.Choice(SUPPORTED_DEP_MANAGERS),
    default=None,
    help="Dependency manager for Lambda runtime."
    + click.style(f"\n\nDependency managers: {', '.join(SUPPORTED_DEP_MANAGERS)}", bold=True),
    required=False,
    cls=ClickMutex,
    replace_help_option="--dependency-manager DEPENDENCY_MANAGER",
    incompatible_params=["location"],
    incompatible_params_hint=INCOMPATIBLE_PARAMS_HINT,
)
@click.option("-o", "--output-dir", type=click.Path(), help="Directory to initialize AWS SAM application.", default=".")
@click.option("-n", "--name", help="Name of AWS SAM Application.")
@click.option(
    "--app-template",
    help="Identifier of the managed application template to be used. "
    "Alternatively, run '$sam init' without options for an interactive workflow.",
    cls=ClickMutex,
    incompatible_params=["location"],
    incompatible_params_hint=INCOMPATIBLE_PARAMS_HINT,
)
@click.option(
    "--no-input",
    is_flag=True,
    default=False,
    help="Disable Cookiecutter prompting and accept default values defined in the cookiecutter config.",
)
@click.option(
    "--extra-context",
    default=None,
    help="Override custom parameters in the template's cookiecutter.json configuration e.g. "
    ""
    '{"customParam1": "customValue1", "customParam2":"customValue2"}'
    """ """,
    required=False,
)
@click.option(
    "--tracing/--no-tracing",
    default=None,
    help="Enable AWS X-Ray tracing for application.",
)
@click.option(
    "--application-insights/--no-application-insights",
    default=None,
    help="Enable CloudWatch Application Insights monitoring for application.",
)
@common_options
@non_interactive_validation
@pass_context
@track_command
@check_newer_version
@print_cmdline_args
def cli(
    ctx,
    no_interactive,
    location,
    package_type,
    runtime,
    architecture,
    base_image,
    dependency_manager,
    output_dir,
    name,
    app_template,
    no_input,
    extra_context,
    tracing,
    application_insights,
    config_file,
    config_env,
):
    """
    `sam init` command entry point
    """
    do_cli(
        ctx,
        no_interactive,
        location,
        PackageType.explicit,
        package_type,
        runtime,
        architecture,
        base_image,
        dependency_manager,
        output_dir,
        name,
        app_template,
        no_input,
        extra_context,
        tracing,
        application_insights,
    )  # pragma: no cover


# pylint: disable=too-many-locals
def do_cli(
    ctx,
    no_interactive,
    location,
    pt_explicit,
    package_type,
    runtime,
    architecture,
    base_image,
    dependency_manager,
    output_dir,
    name,
    app_template,
    no_input,
    extra_context,
    tracing,
    application_insights,
):
    """
    Implementation of the ``cli`` method
    """

    from samcli.commands.exceptions import LambdaImagesTemplateException
    from samcli.commands.init.init_generator import do_generate
    from samcli.commands.init.init_templates import InitTemplates
    from samcli.commands.init.interactive_init_flow import do_interactive

    _deprecate_notification(runtime)

    # check for required parameters
    zip_bool = name and runtime and dependency_manager and app_template
    image_bool = name and pt_explicit and base_image
    if location or zip_bool or image_bool:
        # need to turn app_template into a location before we generate
        templates = InitTemplates()
        if package_type == IMAGE and image_bool:
            runtime = _get_runtime_from_image(base_image)
            if runtime is None:
                raise LambdaImagesTemplateException("Unable to infer the runtime from the base image name")
            options = templates.init_options(package_type, runtime, base_image, dependency_manager)
            if not app_template:
                if len(options) == 1:
                    app_template = options[0].get("appTemplate")
                elif len(options) > 1:
                    raise LambdaImagesTemplateException(
                        "Multiple lambda image application templates found. "
                        "Please specify one using the --app-template parameter."
                    )

        if app_template and not location:
            location = templates.location_from_app_template(
                package_type, runtime, base_image, dependency_manager, app_template
            )
            no_input = True
        extra_context = _get_cookiecutter_template_context(name, runtime, architecture, extra_context)

        if not output_dir:
            output_dir = "."
        do_generate(
            location,
            package_type,
            runtime,
            dependency_manager,
            output_dir,
            name,
            no_input,
            extra_context,
            tracing,
            application_insights,
        )
    else:
        if not (pt_explicit or runtime or dependency_manager or base_image or architecture):
            click.secho(INIT_INTERACTIVE_OPTION_GUIDE, fg="yellow", bold=True)

        # proceed to interactive state machine, which will call do_generate
        do_interactive(
            location,
            pt_explicit,
            package_type,
            runtime,
            architecture,
            base_image,
            dependency_manager,
            output_dir,
            name,
            app_template,
            no_input,
            tracing,
            application_insights,
        )


def _deprecate_notification(runtime):
    from samcli.lib.utils.colors import Colored

    if runtime in DEPRECATED_RUNTIMES:
        message = (
            f"WARNING: {runtime} is no longer supported by AWS Lambda, please update to a newer supported runtime. "
            "For more information please check AWS Lambda Runtime Support Policy: "
            "https://docs.aws.amazon.com/lambda/latest/dg/runtime-support-policy.html"
        )
        LOG.warning(Colored().yellow(message))


def _get_cookiecutter_template_context(name, runtime, architecture, extra_context):
    default_context = {}
    extra_context_dict = {}

    if runtime is not None:
        default_context["runtime"] = runtime

    if name is not None:
        default_context["project_name"] = name

    default_context["architectures"] = {"value": get_architectures(architecture)}
    if extra_context is not None:
        try:
            extra_context_dict = json.loads(extra_context)
        except JSONDecodeError as ex:
            raise click.UsageError(
                "Parse error reading the --extra-context parameter. The value of this parameter must be valid JSON."
            ) from ex

    return {**extra_context_dict, **default_context}
