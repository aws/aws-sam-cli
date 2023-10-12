"""
Pre-pulls lambda base images for arm64 runtimes to fix timeout issues during first local invoke
"""

import logging

from samcli.lib.utils.architecture import ARM64, SUPPORTED_RUNTIMES
from samcli.local.docker.lambda_image import Runtime, LambdaImage
from tests.testing_utils import run_command

LOG = logging.getLogger(__name__)

def pytest_sessionstart(session):
    pre_pull_arm64_images = False
    for pytest_arg in session.config.args:
        if "arm64.py" in pytest_arg:
            LOG.info("Running for arm64 build tests...")
            pre_pull_arm64_images = True
            break

    if not pre_pull_arm64_images:
        LOG.info("Not running for arm64 build tests, skipping pre pulling base images")
        return

    LOG.info("Pulling all arm64 lambda base images for fixing timeout issue during sam local invoke")
    for runtime in [e.value for e in Runtime if ARM64 in SUPPORTED_RUNTIMES[e.value]]:
        image_tag = Runtime.get_image_name_tag(runtime, ARM64)
        full_image = f"{LambdaImage._INVOKE_REPO_PREFIX}/{image_tag}"
        run_command(["docker", "pull", full_image])
