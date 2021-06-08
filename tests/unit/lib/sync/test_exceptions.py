from unittest import TestCase
from unittest.mock import MagicMock, call, patch
from samcli.lib.sync.exceptions import MissingPhysicalResourceError


class TestMissingPhysicalResourceError(TestCase):
    def test_exception(self):
        exception = MissingPhysicalResourceError("A")
        self.assertEqual(exception.resource_identifier, "A")
