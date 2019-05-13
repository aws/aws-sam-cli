"""
Represents Lambda debug entrypoints.
"""

import json

from samcli.local.docker.lambda_image import Runtime


class DebuggingNotSupported(Exception):
    pass


class LambdaDebugEntryPoint(object):

    @staticmethod
    def get_entry_point(debug_port, debug_args_list, runtime, options):

        entrypoint_mapping = {
            Runtime.java8.value:
                ["/usr/bin/java"] +
                debug_args_list +
                [
                    "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=" + str(debug_port),
                    "-XX:MaxHeapSize=2834432k",
                    "-XX:MaxMetaspaceSize=163840k",
                    "-XX:ReservedCodeCacheSize=81920k",
                    "-XX:+UseSerialGC",
                    # "-Xshare:on", doesn't work in conjunction with the debug options
                    "-XX:-TieredCompilation",
                    "-Djava.net.preferIPv4Stack=true",
                    "-jar",
                    "/var/runtime/lib/LambdaJavaRTEntry-1.0.jar"
                ],

            Runtime.dotnetcore20.value:
                ["/var/lang/bin/dotnet"] + \
                debug_args_list + \
                [
                    "/var/runtime/MockBootstraps.dll",
                    "--debugger-spin-wait"
                ],

            Runtime.dotnetcore21.value:
                ["/var/lang/bin/dotnet"] + \
                debug_args_list + \
                [
                    "/var/runtime/MockBootstraps.dll",
                    "--debugger-spin-wait"
                ],
            Runtime.go1x.value:
                ["/var/runtime/aws-lambda-go"] + \
                debug_args_list + \
                [
                    "-debug=true",
                    "-delvePort=" + str(debug_port),
                    "-delvePath=" + options.get("delvePath"),
                ],
            Runtime.nodejs.value:
                ["/usr/bin/node"] + \
                debug_args_list + \
                [
                    "--debug-brk=" + str(debug_port),
                    "--nolazy",
                    "--max-old-space-size=1229",
                    "--max-new-space-size=153",
                    "--max-executable-size=153",
                    "--expose-gc",
                    "/var/runtime/node_modules/awslambda/bin/awslambda",
                ],
            Runtime.nodejs43.value:
                ["/usr/local/lib64/node-v4.3.x/bin/node"] + \
                debug_args_list + \
                [
                    "--debug-brk=" + str(debug_port),
                    "--nolazy",
                    "--max-old-space-size=2547",
                    "--max-semi-space-size=150",
                    "--max-executable-size=160",
                    "--expose-gc",
                    "/var/runtime/node_modules/awslambda/index.js",
                ],
            Runtime.nodejs610.value:
                ["/var/lang/bin/node"] + \
                debug_args_list + \
                [
                    "--debug-brk=" + str(debug_port),
                    "--nolazy",
                    "--max-old-space-size=2547",
                    "--max-semi-space-size=150",
                    "--max-executable-size=160",
                    "--expose-gc",
                    "/var/runtime/node_modules/awslambda/index.js",
                ],
            Runtime.nodejs810.value:
                ["/var/lang/bin/node"] + \
                debug_args_list + \
                [
                    # Node8 requires the host to be explicitly set in order to bind to localhost
                    # instead of 127.0.0.1. https://github.com/nodejs/node/issues/11591#issuecomment-283110138
                    "--inspect-brk=0.0.0.0:" + str(debug_port),
                    "--nolazy",
                    "--expose-gc",
                    "--max-semi-space-size=150",
                    "--max-old-space-size=2707",
                    "/var/runtime/node_modules/awslambda/index.js",
                ],
            Runtime.nodejs10x.value:
                ["/var/rapid/init",
                 "--bootstrap",
                 "/var/lang/bin/node",
                 "--bootstrap-args",
                 json.dumps(debug_args_list +
                            [
                                "--inspect-brk=0.0.0.0:" + str(debug_port),
                                "--nolazy",
                                "--expose-gc",
                                "--max-http-header-size",
                                "81920",
                                "/var/runtime/index.js"
                            ]
                            )
                 ],
            Runtime.python27.value:
                ["/usr/bin/python2.7"] + \
                debug_args_list + \
                [
                    "/var/runtime/awslambda/bootstrap.py"
                ],
            Runtime.python36.value:
                ["/var/lang/bin/python3.6"] +
                debug_args_list + \
                [
                    "/var/runtime/awslambda/bootstrap.py"
                ],
            Runtime.python37.value:
                ["/var/rapid/init",
                 "--bootstrap",
                 "/var/lang/bin/python3.7",
                 "--bootstrap-args",
                 json.dumps(debug_args_list + ["/var/runtime/bootstrap"])
                 ]
        }
        try:
            return entrypoint_mapping[runtime]
        except KeyError:
            raise DebuggingNotSupported(
                "Debugging is not currently supported for {}".format(runtime))
