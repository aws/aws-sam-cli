"""
Module used for detecting whether SAMCLI is executed in a CI/CD environment.
"""

import os
from enum import Enum, auto
from typing import Mapping, Optional, Dict, Union, Callable


class CICDPlatform(Enum):
    Jenkins = auto()
    GitLab = auto()
    GitHubAction = auto()
    TravisCI = auto()
    CircleCI = auto()
    AWSCodeBuild = auto()
    TeamCity = auto()
    Bamboo = auto()
    Buddy = auto()
    CodeShip = auto()
    Semaphore = auto()
    Appveyor = auto()
    # make sure Unknown is at the bottom, it is the fallback.
    Other = auto()


def _is_codeship(environ: Mapping) -> bool:
    """
    Use environ to determine whether it is running in CodeShip.
    According to the doc,
    https://docs.cloudbees.com/docs/cloudbees-codeship/latest/basic-builds-and-configuration/set-environment-variables
    > CI_NAME                # Always CodeShip. Ex: codeship

    to handle both "CodeShip" and "codeship," here the string is converted to lower case first.

    Parameters
    ----------
    environ

    Returns
    -------
    bool
        whether the env is CodeShip
    """
    ci_name: str = environ.get("CI_NAME", "").lower()
    return ci_name == "codeship"


def _is_jenkins(environ: Mapping) -> bool:
    """
    Use environ to determine whether it is running in Jenkins.
    According to the doc,
    https://www.jenkins.io/doc/book/pipeline/jenkinsfile/#working-with-your-jenkinsfile
    > BUILD_TAG
    >   String of jenkins-${JOB_NAME}-${BUILD_NUMBER}.
    > ...
    > JENKINS_URL
    >   Full URL of Jenkins, such as https://example.com:port/jenkins/
    >   (NOTE: only available if Jenkins URL set in "System Configuration")

    Here firstly check JENKINS_URL's presence, if not, then fallback to check BUILD_TAG starts with "jenkins"
    """
    return "JENKINS_URL" in environ or environ.get("BUILD_TAG", "").startswith("jenkins-")


_ENV_VAR_OR_CALLABLE_BY_PLATFORM: Dict[CICDPlatform, Union[str, Callable[[Mapping], bool]]] = {
    CICDPlatform.Jenkins: _is_jenkins,
    # https://docs.gitlab.com/ee/ci/variables/predefined_variables.html
    CICDPlatform.GitLab: "GITLAB_CI",
    # https://docs.github.com/en/actions/reference/environment-variables
    CICDPlatform.GitHubAction: "GITHUB_ACTION",
    # https://docs.travis-ci.com/user/environment-variables/
    CICDPlatform.TravisCI: "TRAVIS",
    # https://circleci.com/docs/2.0/env-vars/
    CICDPlatform.CircleCI: "CIRCLECI",
    # https://docs.aws.amazon.com/codebuild/latest/userguide/build-env-ref-env-vars.html
    CICDPlatform.AWSCodeBuild: "CODEBUILD_BUILD_ID",
    # https://www.jetbrains.com/help/teamcity/predefined-build-parameters.html
    CICDPlatform.TeamCity: "TEAMCITY_VERSION",
    # https://confluence.atlassian.com/bamboo/bamboo-variables-289277087.html
    CICDPlatform.Bamboo: "bamboo_buildNumber",
    # https://buddy.works/docs/pipelines/environment-variables
    CICDPlatform.Buddy: "BUDDY",
    CICDPlatform.CodeShip: _is_codeship,
    # https://docs.semaphoreci.com/ci-cd-environment/environment-variables/
    CICDPlatform.Semaphore: "SEMAPHORE",
    # https://www.appveyor.com/docs/environment-variables/
    CICDPlatform.Appveyor: "APPVEYOR",
    CICDPlatform.Other: "CI",
}


def _is_cicd_platform(cicd_platform: CICDPlatform, environ: Mapping) -> bool:
    """
    Check whether sam-cli run in a particular CI/CD platform based on certain environment variables.

    Parameters
    ----------
    cicd_platform
        an enum CICDPlatform object indicating which CI/CD platform  to check against.
    environ
        the mapping to look for environment variables, for example, os.environ.

    Returns
    -------
    bool
        A boolean indicating whether there are environment variables matching the cicd_platform.
    """
    env_var_or_callable = _ENV_VAR_OR_CALLABLE_BY_PLATFORM[cicd_platform]
    if isinstance(env_var_or_callable, str):
        return env_var_or_callable in environ

    # it is a callable, use the return value
    return env_var_or_callable(environ)


class CICDDetector:
    _cicd_platform: Optional[CICDPlatform]

    def __init__(self):
        try:
            self._cicd_platform: Optional[CICDPlatform] = next(
                cicd_platform for cicd_platform in CICDPlatform if _is_cicd_platform(cicd_platform, os.environ)
            )
        except StopIteration:
            self._cicd_platform = None

    def platform(self) -> Optional[CICDPlatform]:
        """
        Identify which CICD platform SAM CLI is running in.
        Returns
        -------
        CICDPlatform
            an optional CICDPlatform enum indicating the CICD platform.
        """
        return self._cicd_platform
