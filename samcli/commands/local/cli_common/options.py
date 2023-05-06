"""
Common CLI options for invoke command
"""
from pathlib import Path

import click

from samcli.commands._utils.options import docker_click_options, parameter_override_click_option, template_click_option
from samcli.commands.local.cli_common.invoke_context import ContainersInitializationMode


def get_application_dir():
    """

    Returns
    -------
    Path
        Path representing the application config directory
    """
    # TODO: Get the config directory directly from `GlobalConfig`
    return Path(click.get_app_dir("AWS SAM", force_posix=True))


def get_default_layer_cache_dir():
    """
    Default the layer cache directory

    Returns
    -------
    str
        String representing the layer cache directory
    """
    layer_cache_dir = get_application_dir().joinpath("layers-pkg")

    return str(layer_cache_dir)


def local_common_options(f):
    """
    Common CLI options shared by "local invoke", "local start-api", and "local start-lambda" commands

    :param f: Callback passed by Click
    """
    local_options = [
        click.option(
            "--shutdown",
            is_flag=True,
            default=False,
            help="Emulate a shutdown event after invoke completes, " "to test extension handling of shutdown behavior.",
        ),
        click.option(
            "--container-host",
            default="localhost",
            show_default=True,
            help="Host of locally emulated Lambda container. "
            "This option is useful when the container runs on a different host than AWS SAM CLI. "
            "For example, if one wants to run AWS SAM CLI in a Docker container on macOS, "
            "this option could specify `host.docker.internal`",
        ),
        click.option(
            "--container-host-interface",
            default="127.0.0.1",
            show_default=True,
            help="IP address of the host network interface that container ports should bind to. "
            "Use 0.0.0.0 to bind to all interfaces.",
        ),
        click.option(
            "--invoke-image",
            "-ii",
            default=None,
            required=False,
            multiple=True,
            help="Container image URIs for invoking functions or starting api and function. "
            "One can specify the image URI used for the local function invocation "
            "(--invoke-image public.ecr.aws/sam/build-nodejs14.x:latest). "
            "One can also specify for each individual function with "
            "(--invoke-image Function1=public.ecr.aws/sam/build-nodejs14.x:latest). "
            "If a function does not have invoke image specified, the default AWS SAM CLI "
            "emulation image will be used.",
        ),
    ]

    # Reverse the list to maintain ordering of options in help text printed with --help
    for option in reversed(local_options):
        option(f)

    return f


def service_common_options(port):
    """
    Construct common CLI Options that are shared for service related commands ('start-api' and 'start_lambda')

    Parameters
    ----------
    port
        The port number to listen to
    """

    def construct_options(f):
        """
        Common CLI Options that are shared for service related commands ('start-api' and 'start_lambda')

        Parameters
        ----------
        f function
            Callback passed by Click
        port int
            port number to use

        Returns
        -------
        function
            The callback function
        """
        service_options = [
            click.option(
                "--host", default="127.0.0.1", help="Local hostname or IP address to bind to (default: '127.0.0.1')"
            ),
            click.option(
                "--port", "-p", default=port, help="Local port number to listen on (default: '{}')".format(str(port))
            ),
        ]

        # Reverse the list to maintain ordering of options in help text printed with --help
        for option in reversed(service_options):
            option(f)

        return f

    return construct_options


def invoke_common_options(f):
    """
    Common CLI options shared by "local invoke" and "local start-api" commands

    :param f: Callback passed by Click
    """

    invoke_options = (
        [
            template_click_option(),
            click.option(
                "--env-vars",
                "-n",
                type=click.Path(exists=True),
                help="JSON file containing values for Lambda function's environment variables.",
            ),
            parameter_override_click_option(),
            click.option(
                "--debug-port",
                "-d",
                help="When specified, Lambda function container will start in debug mode and will expose this "
                "port on localhost.",
                envvar="SAM_DEBUG_PORT",
                type=click.INT,
                multiple=True,
            ),
            click.option(
                "--debugger-path", help="Host path to a debugger that will be mounted into the Lambda container."
            ),
            click.option(
                "--debug-args", help="Additional arguments to be passed to the debugger.", envvar="DEBUGGER_ARGS"
            ),
            click.option(
                "--container-env-vars",
                type=click.Path(exists=True),
                help="JSON file containing environment variables to be set within the container environment",
            ),
            click.option(
                "--docker-volume-basedir",
                "-v",
                envvar="SAM_DOCKER_VOLUME_BASEDIR",
                help="Specify the location basedir where the SAM template exists. If Docker is running on "
                "a remote machine, Path of the SAM template must be mounted on the Docker machine "
                "and modified to match the remote machine.",
            ),
            click.option("--log-file", "-l", help="File to capture output logs."),
            click.option(
                "--layer-cache-basedir",
                type=click.Path(exists=False, file_okay=False),
                envvar="SAM_LAYER_CACHE_BASEDIR",
                help="Specify the location basedir where the lambda layers used by the template will be downloaded to.",
                default=get_default_layer_cache_dir(),
            ),
        ]
        + docker_click_options()
        + [
            click.option(
                "--force-image-build",
                is_flag=True,
                help="Force rebuilding the image used for invoking functions with layers.",
                envvar="SAM_FORCE_IMAGE_BUILD",
                default=False,
            )
        ]
    )

    # Reverse the list to maintain ordering of options in help text printed with --help
    for option in reversed(invoke_options):
        option(f)

    return f


def warm_containers_common_options(f):
    """
    Warm containers related CLI options shared by "local start-api" and "local start_lambda" commands

    :param f: Callback passed by Click
    """

    warm_containers_options = [
        click.option(
            "--warm-containers",
            help="""
            \b
            Optional. Specifies how AWS SAM CLI manages 
            containers for each function.
            Two modes are available:
            EAGER: Containers for all functions are 
            loaded at startup and persist between 
            invocations.
            LAZY:  Containers are only loaded when each 
            function is first invoked. Those containers 
            persist for additional invocations.
            """,
            type=click.Choice(ContainersInitializationMode.__members__, case_sensitive=False),
        ),
        click.option(
            "--debug-function",
            help="Optional. Specifies the Lambda Function logicalId to apply debug options to when"
            " --warm-containers is specified.  This parameter applies to --debug-port, --debugger-path,"
            " and --debug-args.",
            type=click.STRING,
            multiple=False,
        ),
    ]

    # Reverse the list to maintain ordering of options in help text printed with --help
    for option in reversed(warm_containers_options):
        option(f)

    return f
