import logging

from samcli.lib.utils.architecture import ARM64, SUPPORTED_RUNTIMES
from samcli.local.docker.lambda_image import Runtime, LambdaImage
from tests.testing_utils import run_command

LOG = logging.getLogger(__name__)

def pytest_sessionstart(session):
    LOG.info("Pulling all arm64 lambda base images for fixing timeout issue during sam local invoke")
    for runtime in [e.value for e in Runtime if ARM64 in SUPPORTED_RUNTIMES[e.value]]:
        image_tag = Runtime.get_image_name_tag(runtime, ARM64)
        full_image = f"{LambdaImage._INVOKE_REPO_PREFIX}/{image_tag}"
        run_command(["docker", "pull", full_image])
