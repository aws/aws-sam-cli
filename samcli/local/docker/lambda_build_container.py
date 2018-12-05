"""
Represents Lambda Build Containers.
"""

import json
import logging

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

from .container import Container

LOG = logging.getLogger(__name__)


class LambdaBuildContainer(Container):
    """
    Class to manage Build containers that are capable of building AWS Lambda functions.
    This container mounts necessary folders, issues a command to the Lambda Builder CLI,
    and if the build was successful, copies back artifacts to the host filesystem
    """

    _IMAGE_REPO_NAME = "lambci/lambda"
    _BUILDERS_EXECUTABLE = "lambda-builders"

    def __init__(self,  # pylint: disable=too-many-locals
                 protocol_version,
                 language,
                 dependency_manager,
                 application_framework,
                 source_dir,
                 manifest_path,
                 runtime,
                 optimizations=None,
                 options=None,
                 log_level=None):

        abs_manifest_path = pathlib.Path(manifest_path).resolve()
        manifest_file_name = abs_manifest_path.name
        manifest_dir = str(abs_manifest_path.parent)

        source_dir = str(pathlib.Path(source_dir).resolve())

        container_dirs = LambdaBuildContainer._get_container_dirs(source_dir, manifest_dir)

        request_json = self._make_request(protocol_version,
                                          language,
                                          dependency_manager,
                                          application_framework,
                                          container_dirs,
                                          manifest_file_name,
                                          runtime,
                                          optimizations,
                                          options)

        image = LambdaBuildContainer._get_image(runtime)
        entry = LambdaBuildContainer._get_entrypoint(request_json)
        cmd = []

        additional_volumes = {
            # Manifest is mounted separately in order to support the case where manifest
            # is outside of source directory
            manifest_dir: {
                "bind": container_dirs["manifest_dir"],
                "mode": "ro"
            }
        }

        env_vars = None
        if log_level:
            env_vars = {
                "LAMBDA_BUILDERS_LOG_LEVEL": log_level
            }

        super(LambdaBuildContainer, self).__init__(
            image,
            cmd,
            container_dirs["source_dir"],
            source_dir,
            additional_volumes=additional_volumes,
            entrypoint=entry,
            env_vars=env_vars)

    @property
    def executable_name(self):
        return LambdaBuildContainer._BUILDERS_EXECUTABLE

    @staticmethod
    def _make_request(protocol_version,
                      language,
                      dependency_manager,
                      application_framework,
                      container_dirs,
                      manifest_file_name,
                      runtime,
                      optimizations,
                      options):

        return json.dumps({
            "jsonschema": "2.0",
            "id": 1,
            "method": "LambdaBuilder.build",
            "params": {
                "__protocol_version": protocol_version,
                "capability": {
                    "language": language,
                    "dependency_manager": dependency_manager,
                    "application_framework": application_framework
                },
                "source_dir": container_dirs["source_dir"],
                "artifacts_dir": container_dirs["artifacts_dir"],
                "scratch_dir": container_dirs["scratch_dir"],

                # Path is always inside a Linux container. So '/' is valid
                "manifest_path": "{}/{}".format(container_dirs["manifest_dir"], manifest_file_name),

                "runtime": runtime,
                "optimizations": optimizations,
                "options": options,
            }
        })

    @staticmethod
    def _get_entrypoint(request_json):
        return [LambdaBuildContainer._BUILDERS_EXECUTABLE, request_json]

    @staticmethod
    def _get_container_dirs(source_dir, manifest_dir):
        """
        Provides paths to directories within the container that is required by the builder

        Parameters
        ----------
        source_dir : str
            Path to the function source code

        manifest_dir : str
            Path to the directory containing manifest

        Returns
        -------
        dict
            Contains paths to source, artifacts, scratch & manifest directories
        """
        base = "/tmp/samcli"
        result = {
            "source_dir": "{}/source".format(base),
            "artifacts_dir": "{}/artifacts".format(base),
            "scratch_dir": "{}/scratch".format(base),
            "manifest_dir": "{}/manifest".format(base)
        }

        if pathlib.PurePath(source_dir) == pathlib.PurePath(manifest_dir):
            # It is possible that the manifest resides within the source. In that case, we won't mount the manifest
            # directory separately.
            result["manifest_dir"] = result["source_dir"]

        return result

    @staticmethod
    def _get_image(runtime):
        return "{}:build-{}".format(LambdaBuildContainer._IMAGE_REPO_NAME, runtime)
