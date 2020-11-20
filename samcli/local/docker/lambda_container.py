"""
Represents Lambda runtime containers.
"""
import logging

from pathlib import Path

from samcli.lib.utils.feature_flag import extensions_preview_enabled
from samcli.local.docker.lambda_debug_settings import LambdaDebugSettings
from .container import Container
from .lambda_image import Runtime

LOG = logging.getLogger(__name__)


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
        handler,
        code_dir,
        layers,
        image_builder,
        memory_mb=128,
        env_vars=None,
        debug_options=None,
    ):
        """
        Initializes the class

        Parameters
        ----------
        runtime str
            Name of the Lambda runtime
        handler str
            Handler of the function to run
        code_dir str
            Directory where the Lambda function code is present. This directory will be mounted
            to the container to execute
        layers list(str)
            List of layers
        image_builder samcli.local.docker.lambda_image.LambdaImage
            LambdaImage that can be used to build the image needed for starting the container
        memory_mb int
            Optional. Max limit of memory in MegaBytes this Lambda function can use.
        env_vars dict
            Optional. Dictionary containing environment variables passed to container
        debug_options DebugContext
            Optional. Contains container debugging info (port, debugger path)
        """

        if not Runtime.has_value(runtime):
            raise ValueError("Unsupported Lambda runtime {}".format(runtime))

        image = LambdaContainer._get_image(image_builder, runtime, layers, debug_options)
        ports = LambdaContainer._get_exposed_ports(debug_options)
        entry, debug_env_vars = LambdaContainer._get_debug_settings(runtime, debug_options)
        additional_options = LambdaContainer._get_additional_options(runtime, debug_options)
        additional_volumes = LambdaContainer._get_additional_volumes(runtime, debug_options)
        cmd = []
        if not extensions_preview_enabled():
            cmd = [handler]

        if not env_vars:
            env_vars = {}

        env_vars = {**env_vars, **debug_env_vars}

        super().__init__(
            image,
            cmd,
            self._WORKING_DIR,
            code_dir,
            memory_limit_mb=memory_mb,
            exposed_ports=ports,
            entrypoint=entry,
            env_vars=env_vars,
            container_opts=additional_options,
            additional_volumes=additional_volumes,
        )

    @staticmethod
    def _get_exposed_ports(debug_options):
        """
        Return Docker container port binding information. If a debug port tuple is given, then we will ask Docker to
        bind every given port to same port both inside and outside the container ie. Runtime process is started in debug mode with
        at given port inside the container and exposed to the host machine at the same port

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
    def _get_additional_options(runtime, debug_options):
        """
        Return additional Docker container options. Used by container debug mode to enable certain container
        security options.
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
        :param DebugContext debug_options: DebugContext for the runtime of the container.
        :return dict: Dictionary containing volume map passed to container creation.
        """
        volumes = {}

        if debug_options and debug_options.debugger_path:
            volumes[debug_options.debugger_path] = LambdaContainer._DEBUGGER_VOLUME_MOUNT

        return volumes

    @staticmethod
    def _get_image(image_builder, runtime, layers, debug_options):
        """
        Returns the name of Docker Image for the given runtime

        Parameters
        ----------
        image_builder samcli.local.docker.lambda_image.LambdaImage
            LambdaImage that can be used to build the image needed for starting the container
        runtime str
            Name of the Lambda runtime
        layers list(str)
            List of layers

        Returns
        -------
        str
            Name of Docker Image for the given runtime
        """
        is_debug = bool(debug_options and debug_options.debugger_path)
        return image_builder.build(runtime, layers, is_debug)

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

        entry = "/var/rapid/init"

        if not debug_options:
            return entry, {}

        debug_ports = debug_options.debug_ports
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
            runtime=runtime,
            options=LambdaContainer._DEBUG_ENTRYPOINT_OPTIONS,
        )
