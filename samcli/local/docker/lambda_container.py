"""
Represents Lambda runtime containers.
"""
from enum import Enum

from .container import Container


class Runtime(Enum):
    nodejs = "nodejs"
    nodejs43 = "nodejs4.3"
    nodejs610 = "nodejs6.10"
    nodejs810 = "nodejs8.10"
    python27 = "python2.7"
    python36 = "python3.6"
    java8 = "java8"
    go1x = "go1.x"
    dotnetcore20 = "dotnetcore2.0"

    @classmethod
    def has_value(cls, value):
        """
        Checks if the enum has this value

        :param string value: Value to check
        :return bool: True, if enum has the value
        """
        return any(value == item.value for item in cls)


class LambdaContainer(Container):
    """
    Represents a Lambda runtime container. This class knows how to setup entry points, environment variables,
    exposed ports etc specific to Lambda runtime container. The container management functionality (create/start/stop)
    is provided by the base class
    """

    _IMAGE_REPO_NAME = "lambci/lambda"
    _WORKING_DIR = "/var/task"

    def __init__(self,
                 runtime,
                 handler,
                 code_dir,
                 memory_mb=128,
                 env_vars=None,
                 debug_port=None,
                 debug_args=None):
        """
        Initializes the class

        :param string runtime: Name of the Lambda runtime
        :param string handler: Handler of the function to run
        :param string code_dir: Directory where the Lambda function code is present. This directory will be mounted
            to the container to execute
        :param int memory_mb: Optional. Max limit of memory in MegaBytes this Lambda function can use.
        :param dict env_vars: Optional. Dictionary containing environment variables passed to container
        :param int debug_port: Optional. Bind the runtime's debugger to this port
        :param string debug_args: Optional. Extra arguments passed to the entry point to setup debugging
        """

        if not Runtime.has_value(runtime):
            raise ValueError("Unsupported Lambda runtime {}".format(runtime))

        image = LambdaContainer._get_image(runtime)
        ports = LambdaContainer._get_exposed_ports(debug_port)
        entry = LambdaContainer._get_entry_point(runtime, debug_port, debug_args)
        cmd = [handler]

        super(LambdaContainer, self).__init__(image,
                                              cmd,
                                              self._WORKING_DIR,
                                              code_dir,
                                              memory_limit_mb=memory_mb,
                                              exposed_ports=ports,
                                              entrypoint=entry,
                                              env_vars=env_vars)

    @staticmethod
    def _get_exposed_ports(debug_port):
        """
        Return Docker container port binding information. If a debug port is given, then we will ask Docker to
        bind to same port both inside and outside the container ie. Runtime process is started in debug mode with
        at given port inside the container and exposed to the host machine at the same port

        :param int debug_port: Optional, integer value of debug port
        :return dict: Dictionary containing port binding information. None, if debug_port was not given
        """
        if not debug_port:
            return None

        return {
            # container port : host port
            debug_port: debug_port
        }

    @staticmethod
    def _get_image(runtime):
        """
        Returns the name of Docker Image for the given runtime

        :param string runtime: Name of the runtime
        :return: Name of Docker Image for the given runtime
        """
        return "{}:{}".format(LambdaContainer._IMAGE_REPO_NAME, runtime)

    @staticmethod
    def _get_entry_point(runtime, debug_port=None, debug_args=None):
        """
        Returns the entry point for the container. The default value for the entry point is already configured in the
        Dockerfile. We override this default specifically when enabling debugging. The overridden entry point includes
        a few extra flags to start the runtime in debug mode.

        :param string runtime: Lambda function runtime name
        :param int debug_port: Optional, port for debugger
        :param string debug_args: Optional additional arguments passed to the entry point.
        :return list: List containing the new entry points. Each element in the list is one portion of the command.
            ie. if command is ``node index.js arg1 arg2``, then this list will be ["node", "index.js", "arg1", "arg2"]
        """

        if not debug_port:
            return None

        debug_args_list = []
        if debug_args:
            debug_args_list = debug_args.split(" ")

        # configs from: https://github.com/lambci/docker-lambda
        # to which we add the extra debug mode options
        entrypoint = None
        if runtime == Runtime.java8.value:

            entrypoint = ["/usr/bin/java"] \
                   + debug_args_list \
                   + [
                        "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=" + str(debug_port),
                        "-XX:MaxHeapSize=1336935k",
                        "-XX:MaxMetaspaceSize=157286k",
                        "-XX:ReservedCodeCacheSize=78643k",
                        "-XX:+UseSerialGC",
                        # "-Xshare:on", doesn't work in conjunction with the debug options
                        "-XX:-TieredCompilation",
                        "-Djava.net.preferIPv4Stack=true",
                        "-jar",
                        "/var/runtime/lib/LambdaJavaRTEntry-1.0.jar",
                   ]

        elif runtime == Runtime.nodejs.value:

            entrypoint = ["/usr/bin/node"] \
                   + debug_args_list \
                   + [
                       "--debug-brk=" + str(debug_port),
                       "--nolazy",
                       "--max-old-space-size=1229",
                       "--max-new-space-size=153",
                       "--max-executable-size=153",
                       "--expose-gc",
                       "/var/runtime/node_modules/awslambda/bin/awslambda",
                   ]

        elif runtime == Runtime.nodejs43.value:

            entrypoint = ["/usr/local/lib64/node-v4.3.x/bin/node"] \
                   + debug_args_list \
                   + [
                       "--debug-brk=" + str(debug_port),
                       "--nolazy",
                       "--max-old-space-size=2547",
                       "--max-semi-space-size=150",
                       "--max-executable-size=160",
                       "--expose-gc",
                       "/var/runtime/node_modules/awslambda/index.js",
                   ]

        elif runtime == Runtime.nodejs610.value:

            entrypoint = ["/var/lang/bin/node"] \
                   + debug_args_list \
                   + [
                       "--debug-brk=" + str(debug_port),
                       "--nolazy",
                       "--max-old-space-size=2547",
                       "--max-semi-space-size=150",
                       "--max-executable-size=160",
                       "--expose-gc",
                       "/var/runtime/node_modules/awslambda/index.js",
                   ]

        elif runtime == Runtime.nodejs810.value:

            entrypoint = ["/var/lang/bin/node"] \
                    + debug_args_list \
                    + [
                        # Node8 requires the host to be explicitly set in order to bind to localhost
                        # instead of 127.0.0.1. https://github.com/nodejs/node/issues/11591#issuecomment-283110138
                        "--inspect-brk=0.0.0.0:" + str(debug_port),
                        "--nolazy",
                        "--expose-gc",
                        "--max-semi-space-size=150",
                        "--max-old-space-size=2707",
                        "/var/runtime/node_modules/awslambda/index.js",
                    ]

        elif runtime == Runtime.python27.value:

            entrypoint = ["/usr/bin/python2.7"] \
                   + debug_args_list \
                   + [
                       "/var/runtime/awslambda/bootstrap.py"
                   ]

        elif runtime == Runtime.python36.value:

            entrypoint = ["/var/lang/bin/python3.6"] \
                   + debug_args_list \
                   + [
                       "/var/runtime/awslambda/bootstrap.py"
                   ]

        return entrypoint
