"""
Represents Lambda debug entrypoints.
"""

import logging
from collections import namedtuple

from samcli.local.docker.lambda_image import Runtime


class DebuggingNotSupported(Exception):
    pass


DebugSettings = namedtuple("DebugSettings", ["entrypoint", "container_env_vars"])

LOG = logging.getLogger(__name__)


class LambdaDebugSettings:
    @staticmethod
    def get_debug_settings(debug_port, debug_args_list, _container_env_vars, runtime, options):
        """
        Get Debug settings based on the Runtime

        Parameters
        ----------
        debug_port int
            Port to open for debugging in the container
        debug_args_list list(str)
            Additional debug args
        container_env_vars dict
            Additional debug environmental variables
        runtime str
            Lambda Function runtime
        options dict
            Additonal options needed (i.e delve Path)

        Returns
        -------
        tuple:DebugSettings (list, dict)
            Tuple of debug entrypoint and debug env vars

        """

        entry = ["/var/rapid/aws-lambda-rie", "--log-level", "error"]

        if not _container_env_vars:
            _container_env_vars = dict()

        entrypoint_mapping = {
            Runtime.java8.value: DebugSettings(
                entry,
                container_env_vars={
                    "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address={debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true -Xshare:off"
                    + " ".join(debug_args_list),
                    **_container_env_vars,
                },
            ),
            Runtime.java8al2.value: DebugSettings(
                entry,
                container_env_vars={
                    "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address={debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true -Xshare:off"
                    + " ".join(debug_args_list),
                    **_container_env_vars,
                },
            ),
            Runtime.java11.value: DebugSettings(
                entry,
                container_env_vars={
                    "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=*:{debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true"
                    + " ".join(debug_args_list),
                    **_container_env_vars,
                },
            ),
            Runtime.dotnetcore21.value: DebugSettings(
                entry + ["/var/runtime/bootstrap"] + debug_args_list,
                container_env_vars={"_AWS_LAMBDA_DOTNET_DEBUGGING": "1", **_container_env_vars},
            ),
            Runtime.dotnetcore31.value: DebugSettings(
                entry + ["/var/runtime/bootstrap"] + debug_args_list,
                container_env_vars={"_AWS_LAMBDA_DOTNET_DEBUGGING": "1", **_container_env_vars},
            ),
            Runtime.go1x.value: DebugSettings(
                ["/var/runtime/aws-lambda-go"]
                + debug_args_list
                + ["-debug=true", "-delvePort=" + str(debug_port), "-delvePath=" + options.get("delvePath")],
                container_env_vars=_container_env_vars,
            ),
            Runtime.nodejs10x.value: DebugSettings(
                entry
                + ["/var/lang/bin/node"]
                + debug_args_list
                + ["--no-lazy", "--expose-gc"]
                + ["/var/runtime/index.js"],
                container_env_vars={
                    "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node10/node_modules:/var/runtime/node_module",
                    "NODE_OPTIONS": f"--inspect-brk=0.0.0.0:{str(debug_port)} --max-http-header-size 81920",
                    **_container_env_vars,
                },
            ),
            Runtime.nodejs12x.value: DebugSettings(
                entry
                + ["/var/lang/bin/node"]
                + debug_args_list
                + ["--no-lazy", "--expose-gc"]
                + ["/var/runtime/index.js"],
                container_env_vars={
                    "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node12/node_modules:/var/runtime/node_module",
                    "NODE_OPTIONS": f"--inspect-brk=0.0.0.0:{str(debug_port)} --max-http-header-size 81920",
                    **_container_env_vars,
                },
            ),
            Runtime.python27.value: DebugSettings(
                entry + ["/usr/bin/python2.7"] + debug_args_list + ["/var/runtime/awslambda/bootstrap.py"],
                container_env_vars=_container_env_vars,
            ),
            Runtime.python36.value: DebugSettings(
                entry + ["/var/lang/bin/python3.6"] + debug_args_list + ["/var/runtime/awslambda/bootstrap.py"],
                container_env_vars=_container_env_vars,
            ),
            Runtime.python37.value: DebugSettings(
                entry + ["/var/lang/bin/python3.7"] + debug_args_list + ["/var/runtime/bootstrap"],
                container_env_vars=_container_env_vars,
            ),
            Runtime.python38.value: DebugSettings(
                entry + ["/var/lang/bin/python3.8"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                container_env_vars=_container_env_vars,
            ),
        }
        try:
            return entrypoint_mapping[runtime]
        except KeyError as ex:
            if not runtime:
                LOG.debug("Passing entrypoint as specified in template")
                return DebugSettings(entry + debug_args_list, _container_env_vars)
            raise DebuggingNotSupported("Debugging is not currently supported for {}".format(runtime)) from ex
