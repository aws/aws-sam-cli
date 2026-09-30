"""
Reads user agent information from environment and returns it for telemetry consumption
"""

import os
import re
from typing import Dict, Optional

from samcli.lib.telemetry.agent_detector import Agent, AgentDetector

USER_AGENT_ENV_VAR = "AWS_TOOLING_USER_AGENT"

# Placeholder version emitted for every detected AI agent. Agent CLIs (e.g. Claude
# Code) do not reliably expose their own version through the environment, so we use
# a fixed "1.0" and rely on the agent name for grouping. Bump this only if the
# emitted user-agent format itself needs to change.
AGENT_USER_AGENT_VERSION = "1.0"

# Stable, lowercase-with-dashes names for detected AI agents. These are combined
# with AGENT_USER_AGENT_VERSION to build the user-agent string (e.g.
# "claude-code/1.0") that lands in the queryable "userAgent" telemetry column, so
# they must remain stable across releases to keep downstream queries valid. When
# adding an agent here, also add its detection entry in agent_detector.py.
_USER_AGENT_NAME_BY_AGENT: Dict[Agent, str] = {
    Agent.ClaudeCode: "claude-code",
    Agent.Codex: "codex",
    Agent.Cursor: "cursor",
    Agent.GeminiCLI: "gemini-cli",
    Agent.Antigravity: "antigravity",
    Agent.Kiro: "kiro",
    Agent.OpenCode: "opencode",
    Agent.GitHubCopilot: "github-copilot",
}

# Should accept format: ${AGENT_NAME}/${AGENT_VERSION}
# AWS_Toolkit-For-VSCode/1.62.0
# AWS-Toolkit-For-JetBrains/1.60-223
# AWS-Toolkit-For-JetBrains/1.60.0-223
ACCEPTED_USER_AGENT_FORMAT = re.compile(r"^[A-Za-z0-9\-_]{1,64}/\d+\.\d+(\.\d+)?(\-[A-Za-z0-9]{0,16})?$")


def get_user_agent_string() -> Optional[str]:
    """
    Return the user-agent string for telemetry, or None if none is available.

    Precedence:
      1. AWS_TOOLING_USER_AGENT, when set to a value matching
         ACCEPTED_USER_AGENT_FORMAT. This is set by AWS toolkits (e.g. the VS Code
         and JetBrains toolkits) and always wins when present, so a toolkit
         invocation is still attributed to the toolkit even if it happens to run
         inside an AI agent.
      2. A detected AI agent (e.g. Claude Code), emitted as "<agent-name>/1.0".
         This is used only as a fallback when the toolkit user-agent above is not
         set to a valid value.
    """
    user_agent = os.environ.get(USER_AGENT_ENV_VAR, "").strip()
    if user_agent and ACCEPTED_USER_AGENT_FORMAT.match(user_agent):
        return user_agent

    return _get_agent_user_agent_string()


def _get_agent_user_agent_string() -> Optional[str]:
    """
    Build a "<agent-name>/1.0" user-agent string for the detected AI agent, or None
    when no agent is detected (or the detected agent has no configured name).
    """
    agent = AgentDetector().agent()
    if agent is None:
        return None

    agent_name = _USER_AGENT_NAME_BY_AGENT.get(agent)
    if not agent_name:
        return None

    agent_user_agent = f"{agent_name}/{AGENT_USER_AGENT_VERSION}"
    # Validate against the same format toolkit strings must satisfy, so a
    # misconfigured agent name never emits a malformed user-agent value.
    if ACCEPTED_USER_AGENT_FORMAT.match(agent_user_agent):
        return agent_user_agent
    return None
