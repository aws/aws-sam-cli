"""
Represents Lambda runtime containers.
"""

import logging
import os
from typing import List

from samcli.lib.utils.packagetype import IMAGE
from samcli.local.docker.exceptions import InvalidRuntimeException
from samcli.local.docker.lambda_debug_settings import LambdaDebugSettings

from .container import DEFAULT_CONTAINER_HOST_INTERFACE, Container
from .lambda_image import LambdaImage, Runtime

LOG = logging.getLogger(__name__)

RIE_LOG_LEVEL_ENV_VAR = "SAM_CLI_RIE_DEV"
INVALID_RUNTIME_MESSAGE = "Unsupported Lambda runtime: {runtime}. For a list of supported runtimes, please visit https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html"


class LambdaContainer(Container):
    """
    Represents a Lambda runtime container. This class knows how to setup entry points, environment variables,
    exposed ports etc specific to Lambda runtime container. The container management functionality (create/start/stop)
    is provided by the base class
    """

    _WORKING_DIR = "/var/task"

    # The Volume Mount path for debug files in docker
    _DEBUGGER_VOLUME_MOUNT_PATH = "/tmp/lambci_debug_files"
    _DEFAULT_CONTAINER_DBG_GO_PATH = _DEBUGGER_VOLUME_MOUNT_PATH + "/dlv"

    # Options for selecting debug entry point
    _DEBUG_ENTRYPOINT_OPTIONS = {"delvePath": _DEFAULT_CONTAINER_DBG_GO_PATH}

    # This is the dictionary that represents where the debugger_path arg is mounted in docker to as readonly.
    _DEBUGGER_VOLUME_MOUNT = {"bind": _DEBUGGER_VOLUME_MOUNT_PATH, "mode": "ro"}

    def __init__(
        self,  # pylint: disable=R0914
        runtime,
        imageuri,
        handler,
        packagetype,
        image_config,
        code_dir,
        layers,
        lambda_image,
        architecture,
        memory_mb=128,
        env_vars=None,
        debug_options=None,
        container_host=None,
        container_host_interface=DEFAULT_CONTAINER_HOST_INTERFACE,
        extra_hosts=None,
        function_full_path=None,
        mount_symlinks=False,
    ):
        """
        Initializes the class

        Parameters
        ----------
        runtime str
            Name of the Lambda runtime
        imageuri str
            Location of the Lambda Image which is of the form {image}:{tag}, sha256:{digest},
            or a path to a local archive
        handler str
            Handler of the function to run
        packagetype str
            Package type for the lambda function which is either zip or image.
        image_config dict
            Image configuration which can be used set to entrypoint, command and working dir for the container.
        code_dir str
            Directory where the Lambda function code is present. This directory will be mounted
            to the container to execute
        layers list(str)
            List of layers
        lambda_image samcli.local.docker.lambda_image.LambdaImage
            LambdaImage that can be used to build the image needed for starting the container
        architecture str
            Architecture type either x86_64 or arm64 on AWS lambda
        memory_mb int
            Optional. Max limit of memory in MegaBytes this Lambda function can use.
        env_vars dict
            Optional. Dictionary containing environment variables passed to container
        debug_options DebugContext
            Optional. Contains container debugging info (port, debugger path)
        container_host string
            Optional. Host of locally emulated Lambda container
        container_host_interface
            Optional. Interface that Docker host binds ports to
        extra_hosts
            Optional. Dict of hostname to IP resolutions
        function_full_path str
            Optional. The function full path, unique in all stacks
        mount_symlinks bool
            Optional. True is symlinks should be mounted in the container
        """
        if not Runtime.has_value(runtime) and not packagetype == IMAGE:
            raise InvalidRuntimeException(INVALID_RUNTIME_MESSAGE.format(runtime=runtime))

        image = LambdaContainer._get_image(
            lambda_image, runtime, packagetype, imageuri, layers, architecture, function_full_path
        )
        ports = LambdaContainer._get_exposed_ports(debug_options)
        config = LambdaContainer._get_config(lambda_image, image)
        entry, container_env_vars = LambdaContainer._get_debug_settings(runtime, debug_options)
        additional_options = LambdaContainer._get_additional_options(runtime, debug_options)
        additional_volumes = LambdaContainer._get_additional_volumes(runtime, debug_options)

        _work_dir = self._WORKING_DIR
        _entrypoint = None
        _command = None
        if not env_vars:
            env_vars = {}

        if packagetype == IMAGE:
            _command = (image_config.get("Command") if image_config else None) or config.get("Cmd")
            if not env_vars.get("AWS_LAMBDA_FUNCTION_HANDLER", None):
                # NOTE(sriram-mv):
                # Set AWS_LAMBDA_FUNCTION_HANDLER to be based of the command for Image based Packagetypes.
                env_vars["AWS_LAMBDA_FUNCTION_HANDLER"] = _command[0] if isinstance(_command, list) else None
            _additional_entrypoint_args = (image_config.get("EntryPoint") if image_config else None) or config.get(
                "Entrypoint"
            )
            _entrypoint = entry or self._get_default_entry_point()
            # NOTE(sriram-mv): Only add entrypoint specified in the image configuration if the entrypoint
            # has not changed for debugging.
            if isinstance(_additional_entrypoint_args, list) and entry == self._get_default_entry_point():
                _entrypoint = _entrypoint + _additional_entrypoint_args
            _work_dir = (image_config.get("WorkingDirectory") if image_config else None) or config.get("WorkingDir")

        env_vars = {**env_vars, **container_env_vars}
        super().__init__(
            image,
            _command if _command else [],
            _work_dir,
            code_dir,
            memory_limit_mb=memory_mb,
            exposed_ports=ports,
            entrypoint=_entrypoint if _entrypoint else entry,
            env_vars=env_vars,
            container_opts=additional_options,
            additional_volumes=additional_volumes,
            container_host=container_host,
            container_host_interface=container_host_interface,
            extra_hosts=extra_hosts,
            mount_symlinks=mount_symlinks,
        )

    @staticmethod
    def _get_default_entry_point() -> List[str]:
        """
        Returns default entry point for lambda container, which is the path of the RIE executable with its debugging
        configuration. If SAM_CLI_RIE_DEV is set to 1, RIE log level is set to 'debug', otherwise it is kept as 'error'.
        """
        rie_log_level = "debug" if os.environ.get(RIE_LOG_LEVEL_ENV_VAR, "0") == "1" else "error"
        return ["/var/rapid/aws-lambda-rie", "--log-level", rie_log_level]

    @staticmethod
    def _get_exposed_ports(debug_options):
        """
        Return Docker container port binding information. If a debug port tuple is given, then we will ask Docker to
        bind every given port to same port both inside and outside the container ie.
        Runtime process is started in debug mode with at given port inside the container
        and exposed to the host machine at the same port.

        :param DebugContext debug_options: Debugging options for the function (includes debug port, args, and path)
        :return dict: Dictionary containing port binding information. None, if debug_port was not given
        """
        if not debug_options:
            return None

        if not debug_options.debug_ports:
            return None

        # container port : host port
        ports_map = {}
        for port in debug_options.debug_ports:
            ports_map[port] = port

        return ports_map

    @staticmethod
    def _get_additional_options(runtime: str, debug_options):
        """
        Return additional Docker container options. Used by container debug mode to enable certain container
        security options.
        :param runtime: The runtime string
        :param DebugContext debug_options: DebugContext for the runtime of the container.
        :return dict: Dictionary containing additional arguments to be passed to container creation.
        """
        if not debug_options:
            return None

        opts = {}

        if runtime == Runtime.go1x.value:
            # These options are required for delve to function properly inside a docker container on docker < 1.12
            # See https://github.com/moby/moby/issues/21051
            opts["security_opt"] = ["seccomp:unconfined"]
            opts["cap_add"] = ["SYS_PTRACE"]

        return opts

    @staticmethod
    def _get_additional_volumes(runtime, debug_options):
        """
        Return additional volumes to be mounted in the Docker container. Used by container debug for mapping
        debugger executable into the container.
        :param runtime: the runtime string
        :param DebugContext debug_options: DebugContext for the runtime of the container.
        :return dict: Dictionary containing volume map passed to container creation.
        """
        volumes = {}

        if debug_options and debug_options.debugger_path:
            volumes[debug_options.debugger_path] = LambdaContainer._DEBUGGER_VOLUME_MOUNT

        return volumes

    @staticmethod
    def _get_image(
        lambda_image: LambdaImage,
        runtime: str,
        packagetype: str,
        image: str,
        layers: List[str],
        architecture: str,
        function_name: str,
    ):
        """

        Parameters
        ----------
        lambda_image : LambdaImage
            LambdaImage that can be used to build the image needed for starting the container
        runtime : str
            Name of the Lambda runtime
        packagetype : str
            Package type for the lambda function which is either zip or image.
        image : str
            Location of the Lambda Image which is of the form {image}:{tag}, sha256:{digest},
            or a path to a local archive
        layers : List[str]
            List of layers
        architecture : str
            Architecture type either x86_64 or arm64 on AWS lambda
        function_name: str
            The name of the lambda function that the container is to invoke

        Returns
        -------
        str
            Name of Docker Image for the given runtime
        """
        return lambda_image.build(runtime, packagetype, image, layers, architecture, function_name=function_name)

    @staticmethod
    def _get_config(lambda_image, image):
        return lambda_image.get_config(image)

    @staticmethod
    def _get_debug_settings(runtime, debug_options=None):  # pylint: disable=too-many-branches
        """
        Returns the entry point for the container. The default value for the entry point is already configured in the
        Dockerfile. We override this default specifically when enabling debugging. The overridden entry point includes
        a few extra flags to start the runtime in debug mode.

        :param string runtime: Lambda function runtime name.
        :param DebugContext debug_options: Optional. Debug context for the function (includes port, args, and path).
        :return list: List containing the new entry points. Each element in the list is one portion of the command.
            ie. if command is ``node index.js arg1 arg2``, then this list will be ["node", "index.js", "arg1", "arg2"]
        """

        entry = LambdaContainer._get_default_entry_point()
        if not debug_options:
            return entry, {}

        debug_ports = debug_options.debug_ports
        container_env_vars = debug_options.container_env_vars
        if not debug_ports:
            return entry, {}

        debug_port = debug_ports[0]
        debug_args_list = []

        if debug_options.debug_args:
            debug_args_list = debug_options.debug_args.split(" ")
        # configs from: https://github.com/lambci/docker-lambda
        # to which we add the extra debug mode options
        return LambdaDebugSettings.get_debug_settings(
            debug_port=debug_port,
            debug_args_list=debug_args_list,
            _container_env_vars=container_env_vars,
            runtime=runtime,
            options=LambdaContainer._DEBUG_ENTRYPOINT_OPTIONS,
        )
