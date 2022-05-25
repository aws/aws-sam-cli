import logging
import os
import random
import shutil
import sys
from pathlib import Path
from typing import Set
from unittest import skipIf

import jmespath
import docker
import pytest
from parameterized import parameterized, parameterized_class

from samcli.lib.utils import osutils
from samcli.yamlhelper import yaml_parse
from tests.testing_utils import (
    IS_WINDOWS,
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
    CI_OVERRIDE,
    run_command,
    SKIP_DOCKER_TESTS,
    SKIP_DOCKER_BUILD,
    SKIP_DOCKER_MESSAGE,
)
from .resources_integ_base import ResourcesIntegBase

class TestResources(ResourcesIntegBase):
    def test_