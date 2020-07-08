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
        MountedFileProvider._copy_to_basedir(MountedFileProvider._RAPID_SOURCE, rapid_basedir, "init")
        MountedFileProvider._copy_to_basedir(MountedFileProvider._GO_BOOTSTRAP_SOURCE, go_bootstrap_basedir, "aws-lambda-go")
        self._rapid_basedir = rapid_basedir
        self._go_bootstrap_basedir = go_bootstrap_basedir

    @property
    def rapid_basedir(self):
        return self._rapid_basedir

    @property
    def go_bootstrap_basedir(self):
        return self._go_bootstrap_basedir

    @staticmethod
    def _copy_to_basedir(source, basedir, dest_filename):
        import pdb; pdb.set_trace()
        Path(basedir).mkdir(mode=0o700, parents=True, exist_ok=True)
        dest = Path("{}/{}".format(basedir, dest_filename))
        LOG.debug("Copying from %s to %s.", str(source), str(dest))
        copyfile(source, str(dest))
        st = os.stat(source)
        os.chmod(dest, st.st_mode)
