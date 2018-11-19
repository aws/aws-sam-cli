"""
Common CLI options for invoke command
"""

import click
from samcli.commands._utils.options import template_click_option, docker_click_options, parameter_override_click_option


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
            click.option('--host',
                         default="127.0.0.1",
                         help="Local hostname or IP address to bind to (default: '127.0.0.1')"),
            click.option("--port", "-p",
                         default=port,
                         help="Local port number to listen on (default: '{}')".format(str(port)))
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

    invoke_options = [
        template_click_option(),

        click.option('--env-vars', '-n',
                     type=click.Path(exists=True),
                     help="JSON file containing values for Lambda function's environment variables."),

        parameter_override_click_option(),

        click.option('--debug-port', '-d',
                     help="When specified, Lambda function container will start in debug mode and will expose this "
                          "port on localhost.",
                     envvar="SAM_DEBUG_PORT"),

        click.option('--debugger-path',
                     help="Host path to a debugger that will be mounted into the Lambda container."),

        click.option('--debug-args',
                     help="Additional arguments to be passed to the debugger.",
                     envvar="DEBUGGER_ARGS"),

        click.option('--docker-volume-basedir', '-v',
                     envvar="SAM_DOCKER_VOLUME_BASEDIR",
                     help="Specifies the location basedir where the SAM file exists. If the Docker is running on "
                          "a remote machine, you must mount the path where the SAM file exists on the docker machine "
                          "and modify this value to match the remote machine."),

        click.option('--log-file', '-l',
                     help="logfile to send runtime logs to."),

    ] + docker_click_options() + [

        click.option('--profile',
                     help="Specify which AWS credentials profile to use."),

        click.option('--region',
                     help="Specify which AWS region to use."),

    ]

    # Reverse the list to maintain ordering of options in help text printed with --help
    for option in reversed(invoke_options):
        option(f)

    return f
