from unittest import TestCase
from unittest.mock import MagicMock, patch
from samcli.lib.sync.infra_sync_executor import InfraSyncExecutor
from botocore.exceptions import ClientError
from parameterized import parameterized


class TestInfraSyncExecutor(TestCase):
    pass