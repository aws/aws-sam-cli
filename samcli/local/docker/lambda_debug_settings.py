"""
Represents Lambda debug entrypoints.
"""

import json
from collections import namedtuple

from samcli.lib.utils.feature_flag import extensions_preview_enabled
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

        extensions_preview_on = extensions_preview_enabled()

        if extensions_preview_on:
            entry = ["/var/rapid/init", "--log-level", "error"]
            entrypoint_mapping = {
                Runtime.java8.value: DebugSettings(
                    entry,
                    debug_env_vars={
                        "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address={debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true -Xshare:off"
                        + " ".join(debug_args_list)
                    },
                ),
                Runtime.java11.value: DebugSettings(
                    entry,
                    debug_env_vars={
                        "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=*:{debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true"
                        + " ".join(debug_args_list)
                    },
                ),
                Runtime.dotnetcore21.value: DebugSettings(
                    entry + ["/var/runtime/bootstrap"] + debug_args_list,
                    debug_env_vars={"_AWS_LAMBDA_DOTNET_DEBUGGING": "1"},
                ),
                Runtime.go1x.value: DebugSettings(
                    ["/var/runtime/aws-lambda-go"]
                    + debug_args_list
                    + ["-debug=true", "-delvePort=" + str(debug_port), "-delvePath=" + options.get("delvePath")],
                    debug_env_vars={},
                ),
                Runtime.nodejs10x.value: DebugSettings(
                    entry
                    + ["/var/lang/bin/node"]
                    + debug_args_list
                    + [
                        "/var/runtime/index.js",
                    ],
                    debug_env_vars={
                        "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node10/node_modules:/var/runtime/node_module",
                        "NODE_OPTIONS": f"--inspect-brk=0.0.0.0:{str(debug_port)} --no-lazy --expose-gc --max-http-header-size 81920",
                    },
                ),
                Runtime.nodejs12x.value: DebugSettings(
                    entry
                    + ["/var/lang/bin/node"]
                    + debug_args_list
                    + [
                        "/var/runtime/index.js",
                    ],
                    debug_env_vars={
                        "NODE_PATH": "/opt/nodejs/node_modules:/opt/nodejs/node12/node_modules:/var/runtime/node_module",
                        "NODE_OPTIONS": f"--inspect-brk=0.0.0.0:{str(debug_port)} --no-lazy --expose-gc --max-http-header-size 81920",
                    },
                ),
                Runtime.python27.value: DebugSettings(
                    entry + ["/var/lang/bin/python2.7"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                    debug_env_vars={},
                ),
                Runtime.python36.value: DebugSettings(
                    entry + ["/var/lang/bin/python3.6"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                    debug_env_vars={},
                ),
                Runtime.python37.value: DebugSettings(
                    entry + ["/var/lang/bin/python3.7"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                    debug_env_vars={},
                ),
                Runtime.python38.value: DebugSettings(
                    entry + ["/var/lang/bin/python3.8"] + debug_args_list + ["/var/runtime/bootstrap.py"],
                    debug_env_vars={},
                ),
            }
        else:
            entry = "/var/rapid/init"
            entrypoint_mapping = {
                Runtime.java8.value: DebugSettings(
                    entry,
                    debug_env_vars={
                        "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address={debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true -Xshare:off"
                        + " ".join(debug_args_list)
                    },
                ),
                Runtime.java8al2.value: DebugSettings(
                    entry,
                    debug_env_vars={
                        "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address={debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true -Xshare:off"
                        + " ".join(debug_args_list)
                    },
                ),
                Runtime.java11.value: DebugSettings(
                    entry,
                    debug_env_vars={
                        "_JAVA_OPTIONS": f"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=*:{debug_port} -XX:MaxHeapSize=2834432k -XX:MaxMetaspaceSize=163840k -XX:ReservedCodeCacheSize=81920k -XX:+UseSerialGC -XX:-TieredCompilation -Djava.net.preferIPv4Stack=true"
                        + " ".join(debug_args_list)
                    },
                ),
                Runtime.dotnetcore21.value: DebugSettings(
                    [
                        "/var/rapid/init",
                        "--bootstrap",
                        "/var/runtime/bootstrap",
                        "--bootstrap-args",
                        json.dumps(debug_args_list),
                    ],
                    debug_env_vars={"_AWS_LAMBDA_DOTNET_DEBUGGING": "1"},
                ),
                Runtime.dotnetcore31.value: DebugSettings(
                    [
                        "/var/rapid/init",
                        "--bootstrap",
                        "/var/runtime/bootstrap",
                        "--bootstrap-args",
                        json.dumps(debug_args_list),
                    ],
                    debug_env_vars={"_AWS_LAMBDA_DOTNET_DEBUGGING": "1"},
                ),
                Runtime.go1x.value: DebugSettings(
                    ["/var/runtime/aws-lambda-go"]
                    + debug_args_list
                    + ["-debug=true", "-delvePort=" + str(debug_port), "-delvePath=" + options.get("delvePath")],
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
                    [
                        "/var/rapid/init",
                        "--bootstrap",
                        "/usr/bin/python2.7",
                        "--bootstrap-args",
                        json.dumps(debug_args_list + ["/var/runtime/awslambda/bootstrap.py"]),
                    ],
                    debug_env_vars={},
                ),
                Runtime.python36.value: DebugSettings(
                    [
                        "/var/rapid/init",
                        "--bootstrap",
                        "/var/lang/bin/python3.6",
                        "--bootstrap-args",
                        json.dumps(debug_args_list + ["/var/runtime/awslambda/bootstrap.py"]),
                    ],
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
                        json.dumps(debug_args_list + ["/var/runtime/bootstrap.py"]),
                    ],
                    debug_env_vars={},
                ),
            }
        try:
            return entrypoint_mapping[runtime]
        except KeyError as ex:
            raise DebuggingNotSupported("Debugging is not currently supported for {}".format(runtime)) from ex
