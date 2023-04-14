"""
Reads user agent information from environment and returns it for telemetry consumption
"""
import os
import re
from typing import Optional

USER_AGENT_ENV_VAR = "AWS_TOOLING_USER_AGENT"

# Should accept format: ${AGENT_NAME}/${AGENT_VERSION}
# AWS_Toolkit-For-VSCode/1.62.0
# AWS-Toolkit-For-JetBrains/1.60-223
# AWS-Toolkit-For-JetBrains/1.60.0-223
ACCEPTED_USER_AGENT_FORMAT = re.compile(r"^[A-Za-z0-9\-_]{1,64}/\d+\.\d+(\.\d+)?(\-[A-Za-z0-9]{0,16})?$")


def get_user_agent_string() -> Optional[str]:
    user_agent = os.environ.get(USER_AGENT_ENV_VAR, "").strip()
    if user_agent and ACCEPTED_USER_AGENT_FORMAT.match(user_agent):
        return user_agent
    return None
