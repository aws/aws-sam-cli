"""
Helps to stage mounted file dependencies for Docker containers to user-local folders from source.
"""
import logging
import os
import stat

from pathlib import Path
from shutil import copyfile

LOG = logging.getLogger(__name__)


class MountedFileProvider:

    _RAPID_SOURCE = Path(__file__).parent.joinpath("..", "rapid", "init").resolve()
    _GO_BOOTSTRAP_SOURCE = Path(__file__).parent.joinpath("..", "go-bootstrap", "aws-lambda-go").resolve()

    def __init__(self, rapid_basedir, go_bootstrap_basedir):
        # need to copy files over if not already done
        MountedFileProvider._copy_source_files(rapid_basedir, go_bootstrap_basedir)
        self._rapid_basedir = rapid_basedir
        self._go_bootstrap_basedir = go_bootstrap_basedir

    @property
    def rapid_basedir(self):
        return self._rapid_basedir

    @property
    def go_bootstrap_basedir(self):
        return self._go_bootstrap_basedir

    @staticmethod
    def _copy_source_files(rapid_basedir, go_bootstrap_basedir):
        LOG.debug("Creating basedirs if they do not yet exist.")
        Path(rapid_basedir).mkdir(mode=0o700, parents=True, exist_ok=True)
        Path(go_bootstrap_basedir).mkdir(mode=0o700, parents=True, exist_ok=True)

        rapid_dest = "{}/init".format(rapid_basedir)
        LOG.debug("Copying RAPID stub server from %s to %s.", str(MountedFileProvider._RAPID_SOURCE), rapid_dest)
        copyfile(MountedFileProvider._RAPID_SOURCE, rapid_dest)
        rapid_st = os.stat(MountedFileProvider._RAPID_SOURCE)
        os.chmod(rapid_dest, rapid_st.st_mode)

        go_bootstrap_dest = "{}/aws-lambda-go".format(go_bootstrap_basedir)
        copyfile(MountedFileProvider._GO_BOOTSTRAP_SOURCE, go_bootstrap_dest)
        go_bootstrap_st = os.stat(MountedFileProvider._GO_BOOTSTRAP_SOURCE)
        os.chmod(go_bootstrap_dest, go_bootstrap_st.st_mode)
