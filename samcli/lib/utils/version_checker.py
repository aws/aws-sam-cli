"""
Contains information about newer version checker for SAM CLI
"""
import logging
from datetime import datetime, timedelta
from functools import wraps

import click
from requests import get

from samcli import __version__ as installed_version
from samcli.cli.global_config import GlobalConfig

LOG = logging.getLogger(__name__)

AWS_SAM_CLI_PYPI_ENDPOINT = "https://pypi.org/pypi/aws-sam-cli/json"
AWS_SAM_CLI_INSTALL_DOCS = (
    "https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html"
)
PYPI_CALL_TIMEOUT_IN_SECONDS = 5
DELTA_DAYS = 7


def check_newer_version(func):
    """
    This function returns a wrapped function definition, which checks if there are newer version of SAM CLI available

    Parameters
    ----------
    func: function reference
        Actual function (command) which will be executed

    Returns
    -------
    function reference:
        A wrapped function reference which executes original function and checks newer version of SAM CLI
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        # execute actual command first
        actual_result = func(*args, **kwargs)
        # check and inform newer version if it is available
        _inform_newer_version()

        return actual_result

    return wrapped


def _inform_newer_version(force_check=False) -> None:
    """
    Compares installed SAM CLI version with the up to date version from PyPi,
    and print information if up to date version is different then what is installed now

    It will store last version check time into GlobalConfig, so that it won't be running all the time
    Currently, it will be checking weekly

    Parameters
    ----------
    force_check: bool
        When it is True, it will trigger checking new version of SAM CLI. Default value is False

    """
    # run everything else in try-except block
    global_config = None
    need_to_update_last_check_time = True
    try:
        global_config = GlobalConfig()
        last_version_check = global_config.last_version_check

        if force_check or is_version_check_overdue(last_version_check):
            fetch_and_compare_versions()
        else:
            need_to_update_last_check_time = False
    except Exception as e:
        LOG.debug("New version check failed", exc_info=e)
    finally:
        if need_to_update_last_check_time:
            update_last_check_time()


def fetch_and_compare_versions() -> None:
    """
    Compare current up to date version with the installed one, and inform if a newer version available
    """
    response = get(AWS_SAM_CLI_PYPI_ENDPOINT, timeout=PYPI_CALL_TIMEOUT_IN_SECONDS)
    result = response.json()
    latest_version = result.get("info", {}).get("version", None)
    LOG.debug("Installed version %s, current version %s", installed_version, latest_version)
    if latest_version and installed_version != latest_version:
        click.secho(
            f"\nSAM CLI update available ({latest_version}); ({installed_version} installed)", fg="green", err=True
        )
        click.echo(f"To download: {AWS_SAM_CLI_INSTALL_DOCS}", err=True)


def update_last_check_time() -> None:
    """
    Update last_check_time in GlobalConfig
    """
    try:
        gc = GlobalConfig()
        gc.last_version_check = datetime.utcnow().timestamp()
    except Exception as e:
        LOG.debug("Updating last version check time was failed", exc_info=e)


def is_version_check_overdue(last_version_check) -> bool:
    """
    Check if last version check have been made longer then a week ago

    Parameters
    ----------
    last_version_check: epoch time
        last_version_check epoch time read from GlobalConfig

    Returns
    -------
    bool:
        True if last_version_check is None or older then a week, False otherwise
    """
    if last_version_check is None or type(last_version_check) not in [int, float]:
        return True

    epoch_week_ago = datetime.utcnow() - timedelta(days=DELTA_DAYS)
    return datetime.utcfromtimestamp(last_version_check) < epoch_week_ago
