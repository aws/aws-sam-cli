"""
Init command to scaffold a project app from a template
"""

import contextlib
import json
import logging
import os
import sys
import tempfile
from json import JSONDecodeError

import click

from samcli.cli.cli_config_file import ConfigProvider, configuration_option, save_params_option
from samcli.cli.main import common_options, pass_context, print_cmdline_args
from samcli.commands._utils.click_mutex import ClickMutex
from samcli.commands._utils.constants import SAM_TEMPLATE_FILE_NAMES
from samcli.commands._utils.options import structured_output_option
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

STRUCTURED_OUTPUT_PARAMS_HINT = """--output json cannot be used with the interactive flow, which prompts for values \
that cannot be answered when the output is being consumed by another program. Provide one of the following parameter \
combinations instead:
\t--name, --location, or
\t--name, --package-type, --base-image, or
\t--name, --runtime, --app-template, --dependency-manager
"""

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
    help=HELP_TEXT,
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
    "Alternatively, run '$ sam init' without options for an interactive workflow.",
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
@click.option(
    "--structured-logging/--no-structured-logging",
    default=None,
    help="Enable Structured Logging for application.",
)
@structured_output_option
@common_options
@save_params_option
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
    structured_logging,
    output,
    save_params,
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
        structured_logging,
        output,
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
    structured_logging,
    output="text",
):
    """
    Implementation of the ``cli`` method
    """

    from samcli.commands.exceptions import LambdaImagesTemplateException
    from samcli.commands.init.init_generator import do_generate
    from samcli.commands.init.init_templates import InitTemplates
    from samcli.commands.init.interactive_init_flow import do_interactive
    from samcli.lib.observability.util import OutputOption

    output_mode = OutputOption(output)

    _deprecate_notification(runtime)

    # check for required parameters
    zip_bool = name and runtime and dependency_manager and app_template
    image_bool = name and pt_explicit and base_image
    if location or zip_bool or image_bool:
        try:
            # Inside the try so template-resolution errors (an unresolvable --base-image, ambiguous
            # image templates, a malformed --extra-context) are serialized too, not just failures
            # from do_generate. Mirrors sam build's do_cli, which wraps its option preprocessing.

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
            if output_mode is OutputOption.json:
                # A JSON consumer cannot answer cookiecutter's prompts. The --app-template path
                # already sets no_input above, but --location does not, so force it here as well.
                no_input = True
            captured_stdout = None
            with contextlib.ExitStack() as stack:
                if output_mode is OutputOption.json:
                    # A template's hooks run as subprocesses that write straight to our stdout,
                    # which would leave a JSON consumer with unparseable output. Capture anything
                    # written during generation so it can be re-emitted as JSON below.
                    captured_stdout = stack.enter_context(_capture_stdout())
                generated_directory = do_generate(
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
                    structured_logging,
                )

            if captured_stdout is not None and captured_stdout.text:
                # Stdout is restored by now, so this is safe to emit. Template output is reported
                # rather than discarded, since a hook's instructions can matter to the caller.
                click.echo(json.dumps({"type": "info", "source": "template", "message": captured_stdout.text}))

            if output_mode is OutputOption.json:
                # Report the directory the generator created, as an absolute path so a machine
                # consumer never has to guess the process cwd. output_dir/name is not a usable
                # substitute: a cookiecutter template names its own project directory, so that
                # path is wrong for a --location template used without --name. When the generator
                # could not determine a directory at all, report null rather than a fabricated
                # path. The command still succeeds, matching text mode, but a consumer is told
                # the location is unknown instead of being sent to a directory that may be empty.
                project_directory = os.path.abspath(generated_directory) if generated_directory else None
                click.echo(
                    json.dumps(
                        {
                            "type": "result",
                            "status": "success",
                            "project_directory": project_directory,
                            "template_file": _find_template_file(project_directory) if project_directory else None,
                            "runtime": runtime,
                            # package_type and architectures are only reported for a managed
                            # template, identified by having resolved a runtime. A --location
                            # template decides its own package type and architectures, and the
                            # values we hold there are just defaults (Zip from the --package-type
                            # callback, x86_64 from get_architectures), so reporting them would
                            # look authoritative while contradicting the generated project.
                            "package_type": package_type if runtime else None,
                            "dependency_manager": dependency_manager,
                            "app_template": app_template,
                            "architectures": get_architectures(architecture) if runtime else None,
                        }
                    )
                )
        except click.UsageError:
            # A usage error means the command was called incorrectly and nothing was attempted, so
            # there is no result to describe. Let click report it the way it reports every other
            # usage error, including the --output json guard below: its standard message on stderr
            # and a non-zero exit, with no result document on stdout.
            raise
        except Exception as ex:
            # Broad catch so any execution failure is serialized for a JSON consumer, which has no
            # other way to learn why the command failed. Re-raise so exit codes and @track_command
            # telemetry are unchanged, and so text mode behaves exactly as it did before.
            if output_mode is OutputOption.json:
                click.echo(init_failure_json(ex))
            raise
    else:
        if output_mode is OutputOption.json:
            # sam init prompts by default and those prompts cannot be answered when the output is
            # being consumed by another program. Rejecting here rather than up front keeps any
            # invocation that resolves to the non-interactive path above working, with or without
            # an explicit --no-interactive. Raising before the guide banner below also keeps that
            # text off stdout, where it would corrupt the JSON.
            raise click.UsageError(STRUCTURED_OUTPUT_PARAMS_HINT)
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
            structured_logging,
        )


class CapturedStdout:
    """Holds whatever was written to stdout while _capture_stdout was active."""

    def __init__(self):
        self.text = ""


@contextlib.contextmanager
def _capture_stdout():
    """Redirect stdout into a buffer for the duration of the block.

    Cookiecutter runs a template's hooks as subprocesses that inherit this process's stdout, so
    contextlib.redirect_stdout is not enough here: it only replaces sys.stdout within this
    process. Redirecting file descriptor 1 captures subprocess output as well. A temporary file
    is used rather than a pipe so a hook writing a lot of output cannot fill a pipe and block.

    The captured text is available once the block exits, including when the block raised.

    Yields
    ------
    CapturedStdout
        Object whose ``text`` attribute holds the captured output once the block has exited
    """
    capture = CapturedStdout()
    with tempfile.TemporaryFile(mode="w+") as buffer:
        sys.stdout.flush()
        saved_stdout_fd = os.dup(1)
        try:
            os.dup2(buffer.fileno(), 1)
            yield capture
        finally:
            sys.stdout.flush()
            os.dup2(saved_stdout_fd, 1)
            os.close(saved_stdout_fd)
            buffer.seek(0)
            capture.text = buffer.read().strip()


def _find_template_file(project_directory):
    """Return the absolute path of the generated project's SAM template, or None if it has none.

    A cookiecutter template picks its own template file name, and a project cloned from
    --location may not contain a SAM template at all, so the name cannot be assumed. The
    search order matches get_or_default_template_file_name, so the path reported here is the
    one a subsequent `sam build` in this project would resolve to.

    Parameters
    ----------
    project_directory: str
        An absolute path to the generated project

    Returns
    -------
    Optional[str]
        An absolute path to the template file, or None if the project has no SAM template
    """
    for template_name in SAM_TEMPLATE_FILE_NAMES:
        candidate = os.path.join(project_directory, template_name)
        if os.path.isfile(candidate):
            return candidate

    return None


def init_failure_json(ex):
    """Serialize an init failure into the structured JSON error document.

    Single source of truth for the failure wire format. The shape matches sam build's
    build_failure_json and sam deploy's terminal failure line, so a consumer can handle all
    three commands with one code path. Errors raised during click option processing (bad
    flags, incompatible parameter combinations) surface as click's standard usage output on
    stderr, not as JSON.
    """
    # do_generate re-raises InitErrorException subclasses as UserException(wrapped_from=...), so
    # without this unwrap every failure would flatten to the uninformative "UserException".
    error_type = getattr(ex, "wrapped_from", None) or type(ex).__name__
    return json.dumps(
        {
            "type": "result",
            "status": "failure",
            "error": {"type": error_type, "message": str(ex)},
        }
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
