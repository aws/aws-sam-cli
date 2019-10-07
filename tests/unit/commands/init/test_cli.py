from unittest import TestCase
from mock import patch, ANY

from samcli.commands.init import do_cli as init_cli
from samcli.local.init.exceptions import GenerateProjectFailedError
from samcli.commands.exceptions import UserException


class TestCli(TestCase):
    def setUp(self):
        self.ctx = None
        self.no_interactive = True
        self.location = None
        self.runtime = "python3.6"
        self.dependency_manager = "pip"
        self.output_dir = "."
        self.name = "testing project"
        self.app_template = "hello-world"
        self.no_input = False
        self.extra_context = {'project_name': 'testing project', 'runtime': 'python3.6'}

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli(self, generate_project_patch):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            runtime=self.runtime,
            dependency_manager=self.dependency_manager,
            output_dir=self.output_dir,
            name=self.name,
            app_template=self.app_template,
            no_input=self.no_input,
            auto_clone=False
        )

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY, self.runtime, self.dependency_manager, self.output_dir, self.name, True, self.extra_context
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_generate_project_fails(self, generate_project_patch):

        # GIVEN generate_project fails to create a project
        generate_project_patch.side_effect = GenerateProjectFailedError(
            project=self.name, provider_error="Something wrong happened"
        )

        # WHEN generate_project returns an error
        # THEN we should receive a GenerateProjectFailedError Exception
        with self.assertRaises(UserException):
            init_cli(
                self.ctx,
                no_interactive=self.no_interactive,
                location="self.location",
                runtime=self.runtime,
                dependency_manager=self.dependency_manager,
                output_dir=self.output_dir,
                name=self.name,
                app_template=self.app_template,
                no_input=self.no_input,
                auto_clone=False
            )

            generate_project_patch.assert_called_with(
                self.location, self.runtime, self.dependency_manager, self.output_dir, self.name, self.no_input
            )
