from unittest import TestCase
from unittest.mock import patch, ANY

from click.testing import CliRunner

from samcli.commands.init import cli as init_cmd
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
        self.extra_context = '{"project_name": "testing project", "runtime": "python3.6"}'
        self.extra_context_as_json = {"project_name": "testing project", "runtime": "python3.6"}

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli(self, generate_project_patch, sd_mock):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location=self.location,
            runtime=self.runtime,
            dependency_manager=self.dependency_manager,
            output_dir=None,
            name=self.name,
            app_template=self.app_template,
            no_input=self.no_input,
            extra_context=None,
            auto_clone=False,
        )

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            self.runtime,
            self.dependency_manager,
            self.output_dir,
            self.name,
            True,
            self.extra_context_as_json,
        )

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    def test_init_fails_invalid_template(self, sd_mock):
        # WHEN an unknown app template is passed in
        # THEN an exception should be raised
        with self.assertRaises(UserException):
            init_cli(
                ctx=self.ctx,
                no_interactive=self.no_interactive,
                location=self.location,
                runtime=self.runtime,
                dependency_manager=self.dependency_manager,
                output_dir=None,
                name=self.name,
                app_template="wrong-and-bad",
                no_input=self.no_input,
                extra_context=None,
                auto_clone=False,
            )

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    def test_init_fails_invalid_dep_mgr(self, sd_mock):
        # WHEN an unknown app template is passed in
        # THEN an exception should be raised
        with self.assertRaises(UserException):
            init_cli(
                ctx=self.ctx,
                no_interactive=self.no_interactive,
                location=self.location,
                runtime=self.runtime,
                dependency_manager="bad-wrong",
                output_dir=None,
                name=self.name,
                app_template=self.app_template,
                no_input=self.no_input,
                extra_context=None,
                auto_clone=False,
            )

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_interactive(self, generate_project_patch, sd_mock):
        # WHEN the user follows interactive init prompts

        # 1: selecting managed templates
        # 3: ruby2.5 response to runtime
        # test-project: response to name
        # N: Don't clone/update the source repo
        user_input = """
1
3
test-project
N
        """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)

        # THEN we should receive no errors
        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            "ruby2.5",
            "bundler",
            ".",
            "test-project",
            True,
            {"project_name": "test-project", "runtime": "ruby2.5"},
        )

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_interactive_multiple_dep_mgrs(self, generate_project_patch, sd_mock):
        # WHEN the user follows interactive init prompts

        # 1: selecting managed templates
        # 5: java8 response to runtime
        # 2: gradle as the dependency manager
        # test-project: response to name
        # N: Don't clone/update the source repo
        # 1: hello-word template
        user_input = """
1
5
2
test-project
N
1
        """
        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)

        # THEN we should receive no errors
        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            "java8",
            "gradle",
            ".",
            "test-project",
            True,
            {"project_name": "test-project", "runtime": "java8"},
        )

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_int_with_app_template(self, generate_project_patch, sd_mock):
        # WHEN the user follows interactive init prompts

        # 3: ruby2.5 response to runtime
        # test-project: response to name
        # N: Don't clone/update the source repo
        user_input = """
3
test-project
N
        """
        runner = CliRunner()
        result = runner.invoke(init_cmd, ["--app-template", "hello-world"], input=user_input)

        # THEN we should receive no errors
        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            ANY,
            "ruby2.5",
            "bundler",
            ".",
            "test-project",
            True,
            {"project_name": "test-project", "runtime": "ruby2.5"},
        )

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_int_from_location(self, generate_project_patch, sd_mock):
        # WHEN the user follows interactive init prompts

        # 2: selecting custom location
        # foo: the "location"
        user_input = """
2
foo
        """

        runner = CliRunner()
        result = runner.invoke(init_cmd, input=user_input)

        # THEN we should receive no errors
        self.assertFalse(result.exception)
        generate_project_patch.assert_called_once_with(
            # need to change the location validation check
            "foo",
            None,
            None,
            ".",
            None,
            False,
            None,
        )

    def test_init_cli_missing_params_fails(self):
        # WHEN we call init without necessary parameters
        # THEN we should receive a UserException
        with self.assertRaises(UserException):
            init_cli(
                self.ctx,
                no_interactive=True,
                location=None,
                runtime=None,
                dependency_manager=None,
                output_dir=None,
                name=None,
                app_template=None,
                no_input=True,
                extra_context=None,
                auto_clone=False,
            )

    def test_init_cli_mutually_exclusive_params_fails(self):
        # WHEN we call init without necessary parameters
        # THEN we should receive a UserException
        with self.assertRaises(UserException):
            init_cli(
                self.ctx,
                no_interactive=self.no_interactive,
                location="whatever",
                runtime=self.runtime,
                dependency_manager=self.dependency_manager,
                output_dir=self.output_dir,
                name=self.name,
                app_template="fails-anyways",
                no_input=self.no_input,
                extra_context=None,
                auto_clone=False,
            )

    @patch("samcli.commands.init.init_templates.InitTemplates._shared_dir_check")
    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_generate_project_fails(self, generate_project_patch, sd_mock):

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
                app_template=None,
                no_input=self.no_input,
                extra_context=None,
                auto_clone=False,
            )

            generate_project_patch.assert_called_with(
                self.location, self.runtime, self.dependency_manager, self.output_dir, self.name, self.no_input
            )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_with_extra_context_parameter_not_passed(self, generate_project_patch):
        # GIVEN no extra_context parameter passed
        # WHEN sam init
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
            extra_context=None,
            auto_clone=False,
        )

        # THEN we should receive no errors
        generate_project_patch.assert_called_once_with(
            ANY, self.runtime, self.dependency_manager, ".", self.name, True, self.extra_context_as_json
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_with_extra_context_parameter_passed(self, generate_project_patch):
        # GIVEN extra_context and default_parameter(name, runtime)
        # WHEN sam init
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
            extra_context='{"schema_name":"events", "schema_type":"aws"}',
            auto_clone=False,
        )

        # THEN we should receive no errors and right extra_context should be passed
        generate_project_patch.assert_called_once_with(
            ANY,
            self.runtime,
            self.dependency_manager,
            ".",
            self.name,
            True,
            {"project_name": "testing project", "runtime": "python3.6", "schema_name": "events", "schema_type": "aws"},
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_with_extra_context_not_overriding_default_parameter(self, generate_project_patch):
        # GIVEN default_parameters(name, runtime) and extra_context trying to override default parameter
        # WHEN sam init
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
            extra_context='{"project_name": "my_project", "runtime": "java8", "schema_name":"events", "schema_type": "aws"}',
            auto_clone=False,
        )

        # THEN extra_context should have not overridden default_parameters(name, runtime)
        generate_project_patch.assert_called_once_with(
            ANY,
            self.runtime,
            self.dependency_manager,
            ".",
            self.name,
            True,
            {"project_name": "testing project", "runtime": "python3.6", "schema_name": "events", "schema_type": "aws"},
        )

    def test_init_cli_with_extra_context_input_as_wrong_json_raises_exception(self):
        # GIVEN extra_context as wrong json
        # WHEN a sam init is called
        with self.assertRaises(UserException):
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
                extra_context='{"project_name", "my_project", "runtime": "java8", "schema_name":"events", "schema_type": "aws"}',
                auto_clone=False,
            )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_must_set_default_context_when_location_is_provided(self, generate_project_patch):
        # GIVEN default_parameter(name, runtime) with location
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location="custom location",
            runtime="java8",
            dependency_manager=None,
            output_dir=self.output_dir,
            name="test-project",
            app_template=None,
            no_input=None,
            extra_context='{"schema_name":"events", "schema_type": "aws"}',
            auto_clone=False,
        )

        # THEN should set default parameter(name, runtime) as extra_context
        generate_project_patch.assert_called_once_with(
            "custom location",
            "java8",
            None,
            ".",
            "test-project",
            None,
            {"schema_name": "events", "schema_type": "aws",  "runtime": "java8", "project_name": "test-project"},
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_must_only_set_passed_project_name_when_location_is_provided(self, generate_project_patch):
        # GIVEN only name and extra_context
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location="custom location",
            runtime=None,
            dependency_manager=None,
            output_dir=self.output_dir,
            name="test-project",
            app_template=None,
            no_input=None,
            extra_context='{"schema_name":"events", "schema_type": "aws"}',
            auto_clone=False,
        )

        # THEN extra_context should be without runtime
        generate_project_patch.assert_called_once_with(
            "custom location",
            None,
            None,
            ".",
            "test-project",
            None,
            {"schema_name": "events", "schema_type": "aws", "project_name": "test-project"},
        )

    @patch("samcli.commands.init.init_generator.generate_project")
    def test_init_cli_must_only_set_passed_runtime_when_location_is_provided(self, generate_project_patch):
        # GIVEN only runtime and extra_context
        # WHEN sam init
        init_cli(
            ctx=self.ctx,
            no_interactive=self.no_interactive,
            location="custom location",
            runtime="java8",
            dependency_manager=None,
            output_dir=self.output_dir,
            name=None,
            app_template=None,
            no_input=None,
            extra_context='{"schema_name":"events", "schema_type": "aws"}',
            auto_clone=False,
        )

        # THEN extra_context should be without name
        generate_project_patch.assert_called_once_with(
            "custom location",
            "java8",
            None,
            ".",
            None,
            None,
            {"schema_name": "events", "schema_type": "aws", "runtime": "java8"},
        )
