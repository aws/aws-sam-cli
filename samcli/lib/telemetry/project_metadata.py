"""
Creates and hashes metadata regarding SAM CLI projects.
"""

import hashlib
import re
import subprocess
from os import getcwd
from os.path import basename
from typing import Optional
from urllib.parse import urlparse

from samcli.cli.global_config import GlobalConfig


def get_git_remote_origin_url() -> Optional[str]:
    """
    Retrieve an hashed version of the project's git remote origin url, if it exists.

    Returns
    -------
    str | None
        A SHA256 hexdigest string of the git remote origin url, formatted such that the
        hashed value follows the pattern <hostname>/<owner>/<project_name>.git.
        If telemetry is opted out of by the user, or the `.git` folder is not found
        (the directory is not a git repository), returns None
    """
    if not bool(GlobalConfig().telemetry_enabled):
        return None

    git_url = None
    try:
        runcmd = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"], capture_output=True, shell=True, check=True, text=True
        )
        git_url = _parse_remote_origin_url(str(runcmd.stdout))
    except subprocess.CalledProcessError:
        # Ignoring, None git_url will be handled later
        pass

    return _hash_value(git_url) if git_url else None


def get_project_name() -> Optional[str]:
    """
    Retrieve an hashed version of the project's name, as defined by the .git folder (or directory name if no .git).

    Returns
    -------
    str | None
        A SHA256 hexdigest string of either the name of the project, or the name of the
        current working directory that the command is running in.
        If telemetry is opted out of by the user, returns None
    """
    if not bool(GlobalConfig().telemetry_enabled):
        return None

    project_name = None
    try:
        runcmd = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"], capture_output=True, shell=True, check=True, text=True
        )
        git_url = _parse_remote_origin_url(str(runcmd.stdout))
        if git_url:
            project_name = git_url.split("/")[-1]  # dir is git repo, get project name from URL
    except subprocess.CalledProcessError:
        # Ignoring, None project_name will be handled at the end before returning
        pass

    if not project_name:
        project_name = basename(getcwd().replace("\\", "/"))  # dir is not a git repo, get directory name

    return _hash_value(project_name)


def get_initial_commit_hash() -> Optional[str]:
    """
    Retrieve an hashed version of the project's initial commit hash, if it exists.

    Returns
    -------
    str | None
        A SHA256 hexdigest string of the git project's initial commit hash.
        If telemetry is opted out of by the user, or the `.git` folder is not found
        (the directory is not a git repository), returns None.
    """
    if not bool(GlobalConfig().telemetry_enabled):
        return None

    metadata = None
    try:
        runcmd = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"], capture_output=True, shell=True, check=True, text=True
        )
        metadata = runcmd.stdout.strip()
    except subprocess.CalledProcessError:
        return None  # Not a git repo

    return _hash_value(metadata)


def _parse_remote_origin_url(url: str) -> Optional[str]:
    """
    Parse a `git remote origin url` into a formatted "hostname/project" string

    Returns
    -------
    str
        formatted project origin url
    """
    parsed = urlparse(url)
    if not parsed.path:
        return None

    formatted = (parsed.hostname or "") + parsed.path
    formatted = re.sub(r"\n", "", formatted)
    formatted = re.sub("/$", "", formatted)
    formatted = re.sub(".git$", "", formatted)
    formatted = re.sub("^(.+)@", "", formatted)
    formatted = formatted.replace(":", "/")

    return formatted


def _hash_value(value: str) -> str:
    """Hash a string, and then return the hashed value as a byte string."""
    h = hashlib.sha256()
    h.update(value.encode("utf-8"))
    return h.hexdigest()
