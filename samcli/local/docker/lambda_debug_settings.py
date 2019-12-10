"""
Represents Lambda debug entrypoints.
"""

import json
from collections import namedtuple

from samcli.local.docker.lambda_image import Runtime


class DebuggingNotSupported(Exception):
    pass


DebugSettings = namedtuple("DebugSettings", ["entrypoint", "debug_env_vars"])


class LambdaDebugSettings:
    @staticmethod
    def get_debug_settings(debug_port, debug_args_list, runtime, options):
        """
        Get Debug settings based on the Runtime

        Parameters
        ----------
        debug_port int
            Port to open for debugging in the container
        debug_args_list list(str)
            Additional debug args
        runtime str
            Lambda Function runtime
        options dict
            Additonal options needed (i.e delve Path)

        Returns
        -------
        tuple:DebugSettings (list, dict)
            Tuple of debug entrypoint and debug env vars

        """

        entrypoint_mapping = {
            Runtime.java8.value: DebugSettings(
                entrypoint=["/usr/bin/java"]
                + debug_args_list
                + [
                    "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=" + str(debug_port),
                    "-XX:MaxHeapSize=2834432k",
                    "-XX:MaxMetaspaceSize=163840k",
                    "-XX:ReservedCodeCacheSize=81920k",
                    "-XX:+UseSerialGC",
                    # "-Xshare:on", doesn't work in conjunction with the debug options
                    "-XX:-TieredCompilation",
                    "-Djava.net.preferIPv4Stack=true",
                    "-jar",
                    "/var/runtime/lib/LambdaJavaRTEntry-1.0.jar",
                ],
                debug_env_vars={},
            ),
            Runtime.java11.value: DebugSettings(
                None,
                debug_env_vars={
                    "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=*:{debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true"
                    + " ".join(debug_args_list)
                },
            ),
            Runtime.dotnetcore20.value: DebugSettings(
                ["/var/lang/bin/dotnet"]
                + debug_args_list
                + ["/var/runtime/MockBootstraps.dll", "--debugger-spin-wait"],
                debug_env_vars={},
            ),
            Runtime.dotnetcore21.value: DebugSettings(
                ["/var/lang/bin/dotnet"]
                + debug_args_list
                + ["/var/runtime/MockBootstraps.dll", "--debugger-spin-wait"],
                debug_env_vars={},
            ),
            Runtime.go1x.value: DebugSettings(
                ["/var/runtime/aws-lambda-go"]
                + debug_args_list
                + ["-debug=true", "-delvePort=" + str(debug_port), "-delvePath=" + options.get("delvePath")],
                debug_env_vars={},
            ),
            Runtime.nodejs.value: DebugSettings(
                ["/usr/bin/node"]
                + debug_args_list
                + [
                    "--debug-brk=" + str(debug_port),
                    "--nolazy",
                    "--max-old-space-size=1229",
                    "--max-new-space-size=153",
                    "--max-executable-size=153",
                    "--expose-gc",
                    "/var/runtime/node_modules/awslambda/bin/awslambda",
                ],
                debug_env_vars={},
            ),
            Runtime.nodejs43.value: DebugSettings(
                ["/usr/local/lib64/node-v4.3.x/bin/node"]
                + debug_args_list
                + [
                    "--debug-brk=" + str(debug_port),
                    "--nolazy",
                    "--max-old-space-size=2547",
                    "--max-semi-space-size=150",
                    "--max-executable-size=160",
                    "--expose-gc",
                    "/var/runtime/node_modules/awslambda/index.js",
                ],
                debug_env_vars={},
            ),
            Runtime.nodejs610.value: DebugSettings(
                ["/var/lang/bin/node"]
                + debug_args_list
                + [
                    "--debug-brk=" + str(debug_port),
                    "--nolazy",
                    "--max-old-space-size=2547",
                    "--max-semi-space-size=150",
                    "--max-executable-size=160",
                    "--expose-gc",
                    "/var/runtime/node_modules/awslambda/index.js",
                ],
                debug_env_vars={},
            ),
            Runtime.nodejs810.value: DebugSettings(
                ["/var/lang/bin/node"]
                + debug_args_list
                + [
                    # Node8 requires the host to be explicitly set in order to bind to localhost
                    # instead of 127.0.0.1. https://github.com/nodejs/node/issues/11591#issuecomment-283110138
                    "--inspect-brk=0.0.0.0:" + str(debug_port),
                    "--nolazy",
                    "--expose-gc",
                    "--max-semi-space-size=150",
                    "--max-old-space-size=2707",
                    "/var/runtime/node_modules/awslambda/index.js",
                ],
                debug_env_vars={},
            ),
            Runtime.nodejs10x.value: DebugSettings(
                [
                    "/var/rapid/init",
                    "--bootstrap",
                    "/var/lang/bin/node",
                    "--bootstrap-args",
                    json.dumps(
                        debug_args_list
                        + [
                            "--inspect-brk=0.0.0.0:" + str(debug_port),
                            "--nolazy",
                            "--expose-gc",
                            "--max-http-header-size",
                            "81920",
                            "/var/runtime/index.js",
                        ]
                    ),
                ],
                debug_env_vars={
                    "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node10/node_modules:/var/runtime/node_modules"
                },
            ),
            Runtime.nodejs12x.value: DebugSettings(
                [
                    "/var/rapid/init",
                    "--bootstrap",
                    "/var/lang/bin/node",
                    "--bootstrap-args",
                    json.dumps(
                        debug_args_list
                        + [
                            "--inspect-brk=0.0.0.0:" + str(debug_port),
                            "--nolazy",
                            "--expose-gc",
                            "--max-http-header-size",
                            "81920",
                            "/var/runtime/index.js",
                        ]
                    ),
                ],
                debug_env_vars={
                    "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node12/node_modules:/var/runtime/node_modules"
                },
            ),
            Runtime.python27.value: DebugSettings(
                ["/usr/bin/python2.7"] + debug_args_list + ["/var/runtime/awslambda/bootstrap.py"], debug_env_vars={}
            ),
            Runtime.python36.value: DebugSettings(
                ["/var/lang/bin/python3.6"] + debug_args_list + ["/var/runtime/awslambda/bootstrap.py"],
                debug_env_vars={},
            ),
            Runtime.python37.value: DebugSettings(
                [
                    "/var/rapid/init",
                    "--bootstrap",
                    "/var/lang/bin/python3.7",
                    "--bootstrap-args",
                    json.dumps(debug_args_list + ["/var/runtime/bootstrap"]),
                ],
                debug_env_vars={},
            ),
            Runtime.python38.value: DebugSettings(
                [
                    "/var/rapid/init",
                    "--bootstrap",
                    "/var/lang/bin/python3.8",
                    "--bootstrap-args",
                    json.dumps(debug_args_list + ["/var/runtime/bootstrap"]),
                ],
                debug_env_vars={},
            ),
        }
        try:
            return entrypoint_mapping[runtime]
        except KeyError:
            raise DebuggingNotSupported("Debugging is not currently supported for {}".format(runtime))
