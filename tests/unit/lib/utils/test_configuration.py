from unittest.case import TestCase
from samcli.lib.utils import configuration


class TestConfiguration(TestCase):
    def test_valid_key(self):
        self.assertEqual(
            configuration.get_configuration("app_template_repo_commit"), "773d842c8f721d08c35321defa9087aaabf251f7"
        )

    def test_invalid_key(self):
        self.assertEqual(configuration.get_configuration("non_exist"), "")
