"""
Module used for detecting whether SAMCLI is executed by an AI agent.
"""

import os
from enum import Enum, auto
from typing import Callable, Dict, Mapping, Optional, Union


class Agent(Enum):
    ClaudeCode = auto()
    Codex = auto()
    Cursor = auto()
    GeminiCLI = auto()
    Antigravity = auto()
    Kiro = auto()
    OpenCode = auto()
    GitHubCopilot = auto()


def _is_codex(environ: Mapping) -> bool:
    """
    Whether it is running in Codex (OpenAI's Codex CLI). Codex sets a family of
    CODEX_* variables rather than one canonical var (e.g. CODEX_SANDBOX, CODEX_CI,
    CODEX_THREAD_ID), so match any name starting with "CODEX_".
    """
    return any(key.startswith("CODEX_") for key in environ)


def _is_kiro(environ: Mapping) -> bool:
    """
    Whether it is running in Kiro (the Kiro IDE, via TERM_PROGRAM=kiro, or the Kiro
    CLI, the renamed Amazon Q Developer CLI, via AWS_EXECUTION_ENV). AWS_EXECUTION_ENV
    is shared with AWS Lambda/CloudShell/CodeBuild (e.g. "AWS_Lambda_python3.12"), so
    it is substring-matched on "amazonq"/"kiro", not checked for presence, to avoid
    misattributing those environments.

    NOTE: the "amazonq" substring also matches the genuine Amazon Q Developer CLI.
    Amazon Q is deferred for now, so its CLI runs are attributed to kiro until a
    dedicated Amazon Q agent is added (which must be ordered AFTER Kiro in the enum).
    """
    if environ.get("TERM_PROGRAM", "") == "kiro":
        return True
    aws_execution_env: str = environ.get("AWS_EXECUTION_ENV", "").lower()
    return "amazonq" in aws_execution_env or "kiro" in aws_execution_env


_ENV_VAR_OR_CALLABLE_BY_AGENT: Dict[Agent, Union[str, Callable[[Mapping], bool]]] = {
    # https://docs.anthropic.com/en/docs/claude-code
    Agent.ClaudeCode: "CLAUDECODE",
    # https://developers.openai.com/codex/cli
    Agent.Codex: _is_codex,
    # match presence, not value: the value is not guaranteed stable
    Agent.Cursor: "CURSOR_AGENT",
    # exact name, not a prefix, so GEMINI_CLI_HOME / GEMINI_CLI_NO_RELAUNCH don't match
    Agent.GeminiCLI: "GEMINI_CLI",
    # Google Antigravity CLI (agy); replaces Gemini CLI for consumer users
    Agent.Antigravity: "ANTIGRAVITY_AGENT",
    Agent.Kiro: _is_kiro,
    # OpenCode sets OPENCODE=1 in its root CLI middleware
    Agent.OpenCode: "OPENCODE",
    Agent.GitHubCopilot: "COPILOT_AGENT_SESSION_ID",
}


def _is_agent(agent: Agent, environ: Mapping) -> bool:
    """
    Check whether sam-cli is run by a particular AI agent based on certain environment variables.

    Parameters
    ----------
    agent
        an enum Agent object indicating which AI agent to check against.
    environ
        the mapping to look for environment variables, for example, os.environ.

    Returns
    -------
    bool
        A boolean indicating whether there are environment variables matching the agent.
    """
    env_var_or_callable = _ENV_VAR_OR_CALLABLE_BY_AGENT[agent]
    if isinstance(env_var_or_callable, str):
        return env_var_or_callable in environ

    # it is a callable, use the return value
    return env_var_or_callable(environ)


class AgentDetector:
    _agent: Optional[Agent]

    def __init__(self):
        try:
            self._agent: Optional[Agent] = next(agent for agent in Agent if _is_agent(agent, os.environ))
        except StopIteration:
            self._agent = None

    def agent(self) -> Optional[Agent]:
        """
        Identify which AI agent SAM CLI is running in.
        Returns
        -------
        Agent
            an optional Agent enum indicating the AI agent.
        """
        return self._agent
