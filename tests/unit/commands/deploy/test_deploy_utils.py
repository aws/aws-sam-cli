from unittest import TestCase

import json

from samcli.commands.deploy.utils import hide_noecho_parameter_overrides


class TestPrintDeployArgs(TestCase):
    def test_hide_noecho_parameter_overrides(self):
        test_template_params = {
            "Parameters": {
                "MyHiddenParam": {"Type": "String", "Description": "Hidden Parameter", "NoEcho": True},
                "MyPublicParam": {"Type": "String", "Description": "Hidden Parameter", "NoEcho": False},
            }
        }
        test_parameter_overrides = {"MyHiddenParam": "HiddenVal", "MyPublicParam": "PublicVal"}
        expected_parameter_overrides = {"MyHiddenParam": "*****", "MyPublicParam": "PublicVal"}
        self.assertEqual(
            expected_parameter_overrides,
            hide_noecho_parameter_overrides(test_template_params, test_parameter_overrides),
        )
