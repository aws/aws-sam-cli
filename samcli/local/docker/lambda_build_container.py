"""
Represents Lambda Build Containers.
"""

import json
import logging
import pathlib

from samcli.commands._utils.experimental import get_enabled_experimental_flags
from samcli.local.docker.container import Container

LOG = logging.getLogger(__name__)


class LambdaBuildContainer(Container):
    """
    Class to manage Build containers that are capable of building AWS Lambda functions.
    This container mounts necessary folders, issues a command to the Lambda Builder CLI,
    and if the build was successful, copies back artifacts to the host filesystem
    """

    _IMAGE_URI_PREFIX = "public.ecr.aws/sam/build"
    _IMAGE_TAG = "latest"
    _BUILDERS_EXECUTABLE = "lambda-builders"

    def __init__(  # pylint: disable=too-many-locals
        self,
        protocol_version,
        language,
        dependency_manager,
        application_framework,
        source_dir,
        manifest_path,
        runtime,
        architecture,
        optimizations=None,
        options=None,
        executable_search_paths=None,
        log_level=None,
        mode=None,
        env_vars=None,
        image=None,
        is_building_layer=False,
    ):
        abs_manifest_path = pathlib.Path(manifest_path).resolve()
        manifest_file_name = abs_manifest_path.name
        manifest_dir = str(abs_manifest_path.parent)

        source_dir = str(pathlib.Path(source_dir).resolve())

        container_dirs = LambdaBuildContainer._get_container_dirs(source_dir, manifest_dir)
        env_vars = env_vars if env_vars else {}

        # `executable_search_paths` are provided as a list of paths on the host file system that needs to passed to
        # the builder. But these paths don't exist within the container. We use the following method to convert the
        # host paths to container paths. But if a host path is NOT mounted within the container, we will simply ignore
        # it. In essence, only when the path is already in the mounted path, can the path resolver within the
        # container even find the executable.
        executable_search_paths = LambdaBuildContainer._convert_to_container_dirs(
            host_paths_to_convert=executable_search_paths,
            host_to_container_path_mapping={
                source_dir: container_dirs["source_dir"],
                manifest_dir: container_dirs["manifest_dir"],
            },
        )

        request_json = self._make_request(
            protocol_version,
            language,
            dependency_manager,
            application_framework,
            container_dirs,
            manifest_file_name,
            runtime,
            optimizations,
            options,
            executable_search_paths,
            mode,
            architecture,
            is_building_layer,
        )

        if image is None:
            image = LambdaBuildContainer._get_image(runtime, architecture)
        entry = LambdaBuildContainer._get_entrypoint(request_json)
        cmd = []

        additional_volumes = {
            # Manifest is mounted separately in order to support the case where manifest
            # is outside of source directory
            manifest_dir: {"bind": container_dirs["manifest_dir"], "mode": "ro"}
        }

        if log_level:
            env_vars["LAMBDA_BUILDERS_LOG_LEVEL"] = log_level

        super().__init__(
            image,
            cmd,
            container_dirs["source_dir"],
            source_dir,
            additional_volumes=additional_volumes,
            entrypoint=entry,
            env_vars=env_vars,
        )

    @property
    def executable_name(self):
        return LambdaBuildContainer._BUILDERS_EXECUTABLE

    @staticmethod
    def _make_request(
        protocol_version,
        language,
        dependency_manager,
        application_framework,
        container_dirs,
        manifest_file_name,
        runtime,
        optimizations,
        options,
        executable_search_paths,
        mode,
        architecture,
        is_building_layer,
    ):

        runtime = runtime.replace(".al2", "")

        return json.dumps(
            {
                "jsonschema": "2.0",
                "id": 1,
                "method": "LambdaBuilder.build",
                "params": {
                    "__protocol_version": protocol_version,
                    "capability": {
                        "language": language,
                        "dependency_manager": dependency_manager,
                        "application_framework": application_framework,
                    },
                    "source_dir": container_dirs["source_dir"],
                    "artifacts_dir": container_dirs["artifacts_dir"],
                    "scratch_dir": container_dirs["scratch_dir"],
                    # Path is always inside a Linux container. So '/' is valid
                    "manifest_path": "{}/{}".format(container_dirs["manifest_dir"], manifest_file_name),
                    "runtime": runtime,
                    "optimizations": optimizations,
                    "options": options,
                    "executable_search_paths": executable_search_paths,
                    "mode": mode,
                    "architecture": architecture,
                    "is_building_layer": is_building_layer,
                    "experimental_flags": get_enabled_experimental_flags(),
                },
            }
        )

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
            "manifest_dir": "{}/manifest".format(base),
        }

        if pathlib.PurePath(source_dir) == pathlib.PurePath(manifest_dir):
            # It is possible that the manifest resides within the source. In that case, we won't mount the manifest
            # directory separately.
            result["manifest_dir"] = result["source_dir"]

        return result

    @staticmethod
    def _convert_to_container_dirs(host_paths_to_convert, host_to_container_path_mapping):
        """
        Use this method to convert a list of host paths to a list of equivalent paths within the container
        where the given host path is mounted. This is necessary when SAM CLI needs to pass path information to
        the Lambda Builder running within the container.

        If a host path is not mounted within the container, then this method simply passes the path to the result
        without any changes.

        Ex:
            [ "/home/foo", "/home/bar", "/home/not/mounted"]  => ["/tmp/source", "/tmp/manifest", "/home/not/mounted"]

        Parameters
        ----------
        host_paths_to_convert : list
            List of paths in host that needs to be converted

        host_to_container_path_mapping : dict
            Mapping of paths in host to the equivalent paths within the container

        Returns
        -------
        list
            Equivalent paths within the container
        """

        if not host_paths_to_convert:
            # Nothing to do
            return host_paths_to_convert

        # Make sure the key is absolute host path. Relative paths are tricky to work with because two different
        # relative paths can point to the same directory ("../foo", "../../foo")
        mapping = {str(pathlib.Path(p).resolve()): v for p, v in host_to_container_path_mapping.items()}

        result = []
        for original_path in host_paths_to_convert:
            abspath = str(pathlib.Path(original_path).resolve())

            if abspath in mapping:
                result.append(mapping[abspath])
            else:
                result.append(original_path)
                LOG.debug(
                    "Cannot convert host path '%s' to its equivalent path within the container. "
                    "Host path is not mounted within the container",
                    abspath,
                )

        return result

    @staticmethod
    def _get_image(runtime, architecture):
        """
        Parameters
        ----------
        runtime : str
            Name of the Lambda runtime
        architecture : str
            Architecture type either 'x86_64' or 'arm64

        Returns
        -------
        str
            valid image name
        """
        return f"{LambdaBuildContainer._IMAGE_URI_PREFIX}-{runtime}:" + LambdaBuildContainer.get_image_tag(architecture)

    @staticmethod
    def get_image_tag(architecture):
        """
        Returns the lambda build image tag for an architecture

        Parameters
        ----------
        architecture : str
            Architecture

        Returns
        -------
        str
            Image tag
        """
        return f"{LambdaBuildContainer._IMAGE_TAG}-{architecture}"
