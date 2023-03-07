""" Manage Git repo """

import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path

# import check_output alone so that it can be patched without affecting
# other parts of subprocess.
from subprocess import check_output
from typing import Optional

from samcli.lib.utils import osutils
from samcli.lib.utils.osutils import rmtree_callback

LOG = logging.getLogger(__name__)


class CloneRepoException(Exception):
    """
    Exception class when clone repo fails.
    """


class CloneRepoUnstableStateException(CloneRepoException):
    """
    Exception class when clone repo enters an unstable state.
    """


class ManifestNotFoundException(Exception):
    """
    Exception class when request Manifest file return 404.
    """


class GitRepo:
    """
    Class for managing a Git repo, currently it has a clone functionality only

    Attributes
    ----------
    url: str
        The URL of this Git repository, example "https://github.com/aws/aws-sam-cli"
    local_path: Path
        The path of the last local clone of this Git repository. Can be used in conjunction with clone_attempted
        to avoid unnecessary multiple cloning of the repository.
    clone_attempted: bool
        whether an attempt to clone this Git repository took place or not. Can be used in conjunction with local_path
        to avoid unnecessary multiple cloning of the repository

    Methods
    -------
    clone(self, clone_dir: Path, clone_name, replace_existing=False) -> Path:
        creates a local clone of this Git repository. (more details in the method documentation).
    """

    def __init__(self, url: str) -> None:
        self.url: str = url
        self.local_path: Optional[Path] = None
        self.clone_attempted: bool = False

    @staticmethod
    def _ensure_clone_directory_exists(clone_dir: Path) -> None:
        try:
            clone_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        except OSError as ex:
            LOG.warning("WARN: Unable to create clone directory.", exc_info=ex)
            raise

    @staticmethod
    def git_executable() -> str:
        if platform.system().lower() == "windows":
            executables = ["git", "git.cmd", "git.exe", "git.bat"]
        else:
            executables = ["git"]

        for executable in executables:
            try:
                with subprocess.Popen([executable], stdout=subprocess.PIPE, stderr=subprocess.PIPE):
                    # No exception. Let's pick this
                    return executable
            except OSError as ex:
                LOG.debug("Unable to find executable %s", executable, exc_info=ex)

        raise OSError("Cannot find git, was looking at executables: {}".format(executables))

    def clone(self, clone_dir: Path, clone_name: str, replace_existing: bool = False, commit: str = "") -> Path:
        """
        creates a local clone of this Git repository.
        This method is different from the standard Git clone in the following:
        1. It accepts the path to clone into as a clone_dir (the parent directory to clone in) and a clone_name (The
           name of the local folder) instead of accepting the full path (the join of both) in one parameter
        2. It removes the "*.git" files/directories so the clone is not a GitRepo any more
        3. It has the option to replace the local folder(destination) if already exists

        Parameters
        ----------
        clone_dir: Path
            The directory to create the local clone inside
        clone_name: str
            The dirname of the local clone
        replace_existing: bool
            Whether to replace the current local clone directory if already exists or not
        commit: str
            if a commit is provided, it will checkout out the commit in the clone repo
        Returns
        -------
            The path of the created local clone

        Raises
        ------
        OSError:
            when file management errors like unable to mkdir, copytree, rmtree ...etc
        CloneRepoException:
            General errors like for example; if an error occurred while running `git clone`
            or if the local_clone already exists and replace_existing is not set
        CloneRepoUnstableStateException:
            when reaching unstable state, for example with replace_existing flag set, unstable state can happen
            if removed the current local clone but failed to copy the new one from the temp location to the destination
        """

        GitRepo._ensure_clone_directory_exists(clone_dir=clone_dir)
        # clone to temp then move to the destination(repo_local_path)
        with osutils.mkdir_temp(ignore_errors=True) as tempdir:
            try:
                temp_path = os.path.normpath(os.path.join(tempdir, clone_name))
                git_executable: str = GitRepo.git_executable()
                LOG.info("\nCloning from %s (process may take a moment)", self.url)
                command = [git_executable, "clone", self.url, clone_name]
                if platform.system().lower() == "windows":
                    LOG.debug(
                        "Configure core.longpaths=true in git clone. "
                        "You might also need to enable long paths in Windows registry."
                    )
                    command += ["--config", "core.longpaths=true"]
                check_output(
                    command,
                    cwd=tempdir,
                    stderr=subprocess.STDOUT,
                )

                # bind a certain sam cli release to a specific commit of the aws-sam-cli-app-templates's repo, avoiding
                # regression
                if commit:
                    self._checkout_commit(temp_path, commit)

                self.local_path = self._persist_local_repo(temp_path, clone_dir, clone_name, replace_existing)
                return self.local_path
            except OSError as ex:
                LOG.warning("WARN: Could not clone repo %s", self.url, exc_info=ex)
                raise
            except subprocess.CalledProcessError as clone_error:
                output = clone_error.output.decode("utf-8")
                if "not found" in output.lower():
                    LOG.warning("WARN: Could not clone repo %s", self.url, exc_info=clone_error)
                raise CloneRepoException(output) from clone_error
            finally:
                self.clone_attempted = True

    @staticmethod
    def _persist_local_repo(temp_path: str, dest_dir: Path, dest_name: str, replace_existing: bool) -> Path:
        dest_path = os.path.normpath(dest_dir.joinpath(dest_name))
        try:
            if Path(dest_path).exists():
                if not replace_existing:
                    raise CloneRepoException(f"Can not clone to {dest_path}, directory already exist")
                LOG.debug("Removing old repo at %s", dest_path)
                shutil.rmtree(dest_path, onerror=rmtree_callback)

            LOG.debug("Copying from %s to %s", temp_path, dest_path)
            # Todo consider not removing the .git files/directories
            shutil.copytree(temp_path, dest_path)
            return Path(dest_path)
        except (OSError, shutil.Error) as ex:
            # UNSTABLE STATE
            # it's difficult to see how this scenario could happen except weird permissions, user will need to debug
            msg = (
                "Unstable state when updating repo. "
                f"Check that you have permissions to create/delete files in {dest_dir} directory "
                "or file an issue at https://github.com/aws/aws-sam-cli/issues"
            )

            if platform.system().lower() == "windows":
                msg = (
                    "Failed to modify a local file when cloning app templates. "
                    "MAX_PATH should be enabled in the Windows registry."
                    "\nFor more details on how to enable MAX_PATH for Windows, please visit: "
                    "https://docs.aws.amazon.com/serverless-application-model/latest/"
                    "developerguide/install-sam-cli.html"
                )

            raise CloneRepoUnstableStateException(msg) from ex

    @staticmethod
    def _checkout_commit(repo_dir: str, commit: str):
        try:
            # if the checkout commit failed, it will use the latest commit instead
            git_executable = GitRepo.git_executable()
            check_output(
                [git_executable, "checkout", commit],
                cwd=repo_dir,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as checkout_error:
            output = checkout_error.output.decode("utf-8")
            if "fatal" in output.lower() or "error" in output.lower():
                LOG.warning("WARN: Commit not exist: %s, using the latest one", commit, exc_info=checkout_error)
