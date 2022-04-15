from unittest.case import TestCase
from samcli.lib.utils import configuration


class TestConfiguration(TestCase):
    def test_return_correct_value(self):
        self.assertEqual(configuration.get_app_template_repo_commit(), "773d842c8f721d08c35321defa9087aaabf251f7")
