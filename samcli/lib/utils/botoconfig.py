"""
Automatically add user agent string to boto configs.
"""
from botocore.config import Config

from samcli import __version__
from samcli.cli.global_config import GlobalConfig


def get_boto_config_with_user_agent(**kwargs):
    gc = GlobalConfig()
    return Config(
        user_agent_extra=f"aws-sam-cli/{__version__}/{gc.installation_id}"
        if gc.telemetry_enabled
        else f"aws-sam-cli/{__version__}",
        **kwargs,
    )
