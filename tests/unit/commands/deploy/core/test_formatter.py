from shutil import get_terminal_size
from unittest import TestCase

from samcli.cli.row_modifiers import BaseLineRowModifier
from samcli.commands.deploy.core.formatters import DeployCommandHelpTextFormatter


class TestDeployCommandHelpTextFormatter(TestCase):
    def test_deploy_formatter(self):
        self.formatter = DeployCommandHelpTextFormatter()
        self.assertTrue(self.formatter.left_justification_length <= get_terminal_size().columns // 2)
        self.assertIsInstance(self.formatter.modifiers[0], BaseLineRowModifier)
