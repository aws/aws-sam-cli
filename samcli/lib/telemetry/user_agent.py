"""
Reads user agent information from environment and returns it for telemetry consumption
"""
import os
from typing import Optional

USER_AGENT_ENV_VAR = "AWS_TOOLING_USER_AGENT"


def get_user_agent_string() -> Optional[str]:
    return os.environ.get(USER_AGENT_ENV_VAR)
