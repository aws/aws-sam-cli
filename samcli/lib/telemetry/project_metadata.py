"""
Creates and encrypts metadata regarding SAM CLI projects.
"""

from os import getcwd
from os.path import basename
import re
import subprocess
from uuid import uuid5, NAMESPACE_URL

from samcli.cli.global_config import GlobalConfig


def get_git_origin():
    """
    Retrieve an encrypted version of the project's git remote origin url, if it exists.

    Returns
    -------
    str | None
        A UUID5 encrypted string of the git remote origin url, formatted such that the
        encrypted value follows the pattern <hostname>/<owner>/<project_name>.git.
        If telemetry is opted out of by the user, or the `.git` folder is not found
        (the directory is not a git repository), returns None
    """
    if not bool(GlobalConfig().telemetry_enabled):
        return None

    runcmd = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], capture_output=True, shell=True, check=True, text=True
    )

    if runcmd.returncode:
        return None  # Not a git repo

    metadata = _parse_remote_origin_url(str(runcmd.stdout))
    git_url = "/".join(metadata) + ".git"  # Format to <hostname>/<owner>/<project_name>.git
    return str(uuid5(NAMESPACE_URL, git_url))


def get_project_name():
    """
    Retrieve an encrypted version of the project's name, as defined by the .git folder (or directory name if no .git).

    Returns
    -------
    str | None
        A UUID5 encrypted string of either the name of the project, or the name of the
        current directory that the command is running in.
        If telemetry is opted out of by the user, returns None
    """
    if not bool(GlobalConfig().telemetry_enabled):
        return None

    runcmd = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"], capture_output=True, shell=True, check=True, text=True
    )
    project_name = ""

    if runcmd.returncode:  # Not a git repo. Get dir name instead
        project_name = basename(getcwd().replace("\\", "/"))
    else:
        project_name = _parse_remote_origin_url(str(runcmd.stdout))[2]

    return str(uuid5(NAMESPACE_URL, project_name))


def get_initial_commit():
    """
    Retrieve an encrypted version of the project's initial commit hash, if it exists.

    Returns
    -------
    str | None
        A UUID5 encrypted string of the git project's initial commit hash.
        If telemetry is opted out of by the user, or the `.git` folder is not found
        (the directory is not a git repository), returns None.
    """
    if not bool(GlobalConfig().telemetry_enabled):
        return None

    runcmd = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"], capture_output=True, shell=True, check=True, text=True
    )

    if runcmd.returncode:
        return None  # Not a git repo

    metadata = runcmd.stdout.strip()
    return str(uuid5(NAMESPACE_URL, metadata))


def _parse_remote_origin_url(url: str):
    """
    Parse a `git remote origin url` into its hostname, owner, and project name.

    Returns
    -------
    A list of 3 strings, with indeces corresponding to 0:hostname, 1:owner, 2:project_name
    """
    pattern = re.compile(r"(?:https?://|git@)(?P<hostname>\S*)(?:/|:)(?P<owner>\S*)/(?P<project_name>\S*)\.git")
    return pattern.findall(url)[0]
