import os
from samcli.cli.global_config import GlobalConfig

DOCKER_MIN_API_VERSION = os.environ.get(GlobalConfig.DOCKER_API_ENV_VAR, "1.35")
DOCKER_MIN_API_VERSION_FALLBACK = "1.44"
