"""
Context object used by build command
"""

import os
import shutil

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

from samcli.local.docker.manager import ContainerManager
from samcli.commands.local.lib.sam_function_provider import SamFunctionProvider
from samcli.commands._utils.template import get_template_data
from samcli.commands.exceptions import UserException


class BuildContext(object):

    # Build directories need not be world writable.
    # This is usually a optimal permission for directories
    _BUILD_DIR_PERMISSIONS = 0o755

    def __init__(self,
                 template_file,
                 base_dir,
                 build_dir,
                 manifest_path=None,
                 clean=False,
                 use_container=False,
                 parameter_overrides=None,
                 docker_network=None,
                 skip_pull_image=False):

        self._template_file = template_file
        self._base_dir = base_dir
        self._build_dir = build_dir
        self._manifest_path = manifest_path
        self._clean = clean
        self._use_container = use_container
        self._parameter_overrides = parameter_overrides
        self._docker_network = docker_network
        self._skip_pull_image = skip_pull_image

        self._function_provider = None
        self._template_dict = None
        self._app_builder = None
        self._container_manager = None

    def __enter__(self):
        try:
            self._template_dict = get_template_data(self._template_file)
        except ValueError as ex:
            raise UserException(str(ex))

        self._function_provider = SamFunctionProvider(self._template_dict, self._parameter_overrides)

        if not self._base_dir:
            # Base directory, if not provided, is the directory containing the template
            self._base_dir = str(pathlib.Path(self._template_file).resolve().parent)

        self._build_dir = self._setup_build_dir(self._build_dir, self._clean)

        if self._use_container:
            self._container_manager = ContainerManager(docker_network_id=self._docker_network,
                                                       skip_pull_image=self._skip_pull_image)

        return self

    def __exit__(self, *args):
        pass

    @staticmethod
    def _setup_build_dir(build_dir, clean):

        # Get absolute path
        build_dir = str(pathlib.Path(build_dir).resolve())

        if not pathlib.Path(build_dir).exists():
            # Build directory does not exist. Create the directory and all intermediate paths
            os.makedirs(build_dir, BuildContext._BUILD_DIR_PERMISSIONS)

        if os.listdir(build_dir) and clean:
            # Build folder contains something inside. Clear everything.
            shutil.rmtree(build_dir)
            # this would have cleared the parent folder as well. So recreate it.
            os.mkdir(build_dir, BuildContext._BUILD_DIR_PERMISSIONS)

        return build_dir

    @property
    def container_manager(self):
        return self._container_manager

    @property
    def function_provider(self):
        return self._function_provider

    @property
    def template_dict(self):
        return self._template_dict

    @property
    def build_dir(self):
        return self._build_dir

    @property
    def base_dir(self):
        return self._base_dir

    @property
    def use_container(self):
        return self._use_container

    @property
    def output_template_path(self):
        return os.path.join(self._build_dir, "template.yaml")

    @property
    def original_template_path(self):
        return os.path.abspath(self._template_file)

    @property
    def manifest_path_override(self):
        if self._manifest_path:
            return os.path.abspath(self._manifest_path)

        return None
