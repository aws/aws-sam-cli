from unittest.case import TestCase
from samcli.lib.utils import configuration


class TestConfiguration(TestCase):
    def test_return_correct_value(self):
        self.assertEqual(configuration.get_app_template_repo_commit(), "09b7de41c32ee5f50ec8ceeec4a304534767844b")
