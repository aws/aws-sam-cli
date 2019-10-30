"""
Common CLI options for invoke command
"""
from pathlib import Path

import click

from samcli.commands._utils.options import template_click_option, docker_click_options, parameter_override_click_option


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


def service_common_options(port):
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
                "--docker-volume-basedir",
                "-v",
                envvar="SAM_DOCKER_VOLUME_BASEDIR",
                help="Specifies the location basedir where the SAM file exists. If the Docker is running on "
                "a remote machine, you must mount the path where the SAM file exists on the docker machine "
                "and modify this value to match the remote machine.",
            ),
            click.option("--log-file", "-l", help="logfile to send runtime logs to."),
            click.option(
                "--layer-cache-basedir",
                type=click.Path(exists=False, file_okay=False),
                envvar="SAM_LAYER_CACHE_BASEDIR",
                help="Specifies the location basedir where the Layers your template uses will be downloaded to.",
                default=get_default_layer_cache_dir(),
            ),
        ]
        + docker_click_options()
        + [
            click.option(
                "--force-image-build",
                is_flag=True,
                help="Specify whether CLI should rebuild the image used for invoking functions with layers.",
                envvar="SAM_FORCE_IMAGE_BUILD",
                default=False,
            )
        ]
    )

    # Reverse the list to maintain ordering of options in help text printed with --help
    for option in reversed(invoke_options):
        option(f)

    return f
