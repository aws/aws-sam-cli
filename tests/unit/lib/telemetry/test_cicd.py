from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.lib.telemetry.cicd import CICDPlatform, _is_cicd_platform


class TestCICD(TestCase):
    @parameterized.expand(
        [
            (CICDPlatform.Jenkins, "BUILD_TAG", "jenkins-jobname-123"),
            (CICDPlatform.Jenkins, "JENKINS_URL", Mock()),
            (CICDPlatform.GitLab, "GITLAB_CI", Mock()),
            (CICDPlatform.GitHubAction, "GITHUB_ACTION", Mock()),
            (CICDPlatform.TravisCI, "TRAVIS", Mock()),
            (CICDPlatform.CircleCI, "CIRCLECI", Mock()),
            (CICDPlatform.AWSCodeBuild, "CODEBUILD_BUILD_ID", Mock()),
            (CICDPlatform.TeamCity, "TEAMCITY_VERSION", Mock()),
            (CICDPlatform.Bamboo, "bamboo_buildNumber", Mock()),
            (CICDPlatform.Buddy, "BUDDY", Mock()),
            (CICDPlatform.CodeShip, "CI_NAME", "CodeShip"),
            (CICDPlatform.Semaphore, "SEMAPHORE", Mock()),
            (CICDPlatform.Appveyor, "APPVEYOR", Mock()),
            (CICDPlatform.Other, "CI", Mock()),
        ]
    )
    def test_is_cicd_platform(self, cicd_platform, env_var, env_var_value):
        self.assertTrue(_is_cicd_platform(cicd_platform, {env_var: env_var_value}))

    @parameterized.expand(
        [
            (CICDPlatform.Jenkins, "BUILD_TAG", "not-jenkins-"),
            (CICDPlatform.CodeShip, "CI_NAME", "not-CodeShip"),
        ]
    )
    def test_is_not_cicd_platform(self, cicd_platform, env_var, env_var_value):
        self.assertFalse(_is_cicd_platform(cicd_platform, {env_var: env_var_value}))
