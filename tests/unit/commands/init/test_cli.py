from unittest import TestCase
from mock import patch

from samcli.commands.init import do_cli as init_cli
from samcli.local.init.exceptions import GenerateProjectFailedError
from samcli.commands.exceptions import UserException


class TestCli(TestCase):

    def setUp(self):
        self.ctx = None
        self.location = None
        self.runtime = "python3.6"
        self.output_dir = "."
        self.name = "testing project"
        self.no_input = False

    @patch("samcli.commands.init.generate_project")
    def test_init_cli(self, generate_project_patch):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        init_cli(
            ctx=self.ctx, location=self.location, runtime=self.runtime, output_dir=self.output_dir,
            name=self.name, no_input=self.no_input)

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
                self.location, self.runtime,
                self.output_dir, self.name, self.no_input)

    @patch("samcli.commands.init.generate_project")
    def test_init_cli_generate_project_fails(self, generate_project_patch):

        # GIVEN generate_project fails to create a project
        generate_project_patch.side_effect = GenerateProjectFailedError(
                project=self.name, provider_error="Something wrong happened"
        )

        # WHEN generate_project returns an error
        # THEN we should receive a GenerateProjectFailedError Exception
        with self.assertRaises(UserException):
            init_cli(
                    self.ctx, location="self.location", runtime=self.runtime,
                    output_dir=self.output_dir, name=self.name, no_input=self.no_input)

            generate_project_patch.assert_called_with(
                    self.location, self.runtime,
                    self.output_dir, self.name, self.no_input)
