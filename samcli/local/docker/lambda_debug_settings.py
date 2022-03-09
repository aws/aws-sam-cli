"""
Represents Lambda debug entrypoints.
"""

import logging
from argparse import ArgumentParser
from collections import namedtuple
from typing import List, cast

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

        # The value of entrypoint_mapping is a callable instead of DebugSettings
        # so that DebugSetting objects are not always created.
        entrypoint_mapping = {
            Runtime.java8.value: lambda: DebugSettings(
                entry,
                container_env_vars={
                    "_JAVA_OPTIONS": "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,"
                    f"address={debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k "
                    "-XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation "
                    "-Djava.net.preferIPv4Stack=true -Xshare:off" + " ".join(debug_args_list),
                    **_container_env_vars,
                },
            ),
            Runtime.java8al2.value: lambda: DebugSettings(
                entry,
                container_env_vars={
                    "_JAVA_OPTIONS": "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,"
                    f"address={debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k "
                    "-XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation "
                    "-Djava.net.preferIPv4Stack=true -Xshare:off" + " ".join(debug_args_list),
                    **_container_env_vars,
                },
            ),
            Runtime.java11.value: lambda: DebugSettings(
                entry,
                container_env_vars={
                    "_JAVA_OPTIONS": "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,"
                    f"address=*:{debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k "
                    "-XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation "
                    "-Djava.net.preferIPv4Stack=true" + " ".join(debug_args_list),
                    **_container_env_vars,
                },
            ),
            Runtime.dotnetcore31.value: lambda: DebugSettings(
                entry + ["/var/runtime/bootstrap"] + debug_args_list,
                container_env_vars={"_AWS_LAMBDA_DOTNET_DEBUGGING": "1", **_container_env_vars},
            ),
            Runtime.dotnet6.value: lambda: DebugSettings(
                entry + ["/var/runtime/bootstrap"] + debug_args_list,
                container_env_vars={"_AWS_LAMBDA_DOTNET_DEBUGGING": "1", **_container_env_vars},
            ),
            Runtime.go1x.value: lambda: DebugSettings(
                entry,
                container_env_vars={
                    "_AWS_LAMBDA_GO_DEBUGGING": "1",
                    "_AWS_LAMBDA_GO_DELVE_API_VERSION": LambdaDebugSettings.parse_go_delve_api_version(debug_args_list),
                    "_AWS_LAMBDA_GO_DELVE_LISTEN_PORT": debug_port,
                    "_AWS_LAMBDA_GO_DELVE_PATH": options.get("delvePath"),
                    **_container_env_vars,
                },
            ),
            Runtime.nodejs12x.value: lambda: DebugSettings(
                entry
                + ["/var/lang/bin/node"]
                + debug_args_list
                + ["--no-lazy", "--expose-gc"]
                + ["/var/runtime/index.js"],
                container_env_vars={
                    "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node12/node_modules:/var/runtime/node_modules:"
                    "/var/runtime:/var/task",
                    "NODE_OPTIONS": f"--inspect-brk=0.0.0.0:{str(debug_port)} --max-http-header-size 81920",
                    "AWS_EXECUTION_ENV": "AWS_Lambda_nodejs12.x",
                    **_container_env_vars,
                },
            ),
            Runtime.nodejs14x.value: lambda: DebugSettings(
                entry
                + ["/var/lang/bin/node"]
                + debug_args_list
                + ["--no-lazy", "--expose-gc"]
                + ["/var/runtime/index.js"],
                container_env_vars={
                    "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node14/node_modules:/var/runtime/node_modules:"
                    "/var/runtime:/var/task",
                    "NODE_OPTIONS": f"--inspect-brk=0.0.0.0:{str(debug_port)} --max-http-header-size 81920",
                    "AWS_EXECUTION_ENV": "AWS_Lambda_nodejs14.x",
                    **_container_env_vars,
                },
            ),
            Runtime.python36.value: lambda: DebugSettings(
                entry + ["/var/lang/bin/python3.6"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                container_env_vars=_container_env_vars,
            ),
            Runtime.python37.value: lambda: DebugSettings(
                entry + ["/var/lang/bin/python3.7"] + debug_args_list + ["/var/runtime/bootstrap"],
                container_env_vars=_container_env_vars,
            ),
            Runtime.python38.value: lambda: DebugSettings(
                entry + ["/var/lang/bin/python3.8"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                container_env_vars=_container_env_vars,
            ),
            Runtime.python39.value: lambda: DebugSettings(
                entry + ["/var/lang/bin/python3.9"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                container_env_vars=_container_env_vars,
            ),
        }
        try:
            return entrypoint_mapping[runtime]()
        except KeyError as ex:
            if not runtime:
                LOG.debug("Passing entrypoint as specified in template")
                return DebugSettings(entry + debug_args_list, _container_env_vars)
            raise DebuggingNotSupported("Debugging is not currently supported for {}".format(runtime)) from ex

    @staticmethod
    def parse_go_delve_api_version(debug_args_list: List[str]) -> int:
        parser = ArgumentParser("Parser for delve args")
        parser.add_argument("-delveAPI", type=int, default=1)
        args, unknown_args = parser.parse_known_args(debug_args_list)
        if unknown_args:
            LOG.warning('Ignoring unrecognized arguments: %s. Only "-delveAPI" is supported.', unknown_args)
        return cast(int, args.delveAPI)
