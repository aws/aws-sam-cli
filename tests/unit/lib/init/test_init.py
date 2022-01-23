from unittest import TestCase
from unittest.mock import patch

from pathlib import Path
from cookiecutter.exceptions import CookiecutterException, RepositoryNotFound
from parameterized import parameterized

from samcli.lib.init import generate_project, InvalidLocationError
from samcli.lib.init import GenerateProjectFailedError
from samcli.lib.init import RUNTIME_DEP_TEMPLATE_MAPPING
from samcli.lib.utils.packagetype import ZIP


class TestInit(TestCase):
    def setUp(self):
        self.location = None
        self.runtime = "python3.6"
        self.dependency_manager = "pip"
        self.output_dir = "mydir"
        self.name = "testing project"
        self.no_input = True
        self.extra_context = {"project_name": "testing project", "runtime": self.runtime}
        self.template = RUNTIME_DEP_TEMPLATE_MAPPING["python"][0]["init_location"]

    @patch("samcli.lib.init.cookiecutter")
    def test_init_successful(self, cookiecutter_patch):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        generate_project(
            location=self.location,
            runtime=self.runtime,
            package_type=ZIP,
            dependency_manager=self.dependency_manager,
            output_dir=self.output_dir,
            name=self.name,
            no_input=self.no_input,
        )

        # THEN we should receive no errors
        cookiecutter_patch.assert_called_once_with(
            no_input=self.no_input, output_dir=self.output_dir, template=self.template
        )

    @patch("samcli.lib.init.cookiecutter")
    def test_init_successful_with_no_dep_manager(self, cookiecutter_patch):
        generate_project(
            location=self.location,
            runtime=self.runtime,
            package_type=ZIP,
            dependency_manager=None,
            output_dir=self.output_dir,
            name=self.name,
            no_input=self.no_input,
        )

        # THEN we should receive no errors
        cookiecutter_patch.assert_called_once_with(
            no_input=self.no_input, output_dir=self.output_dir, template=self.template
        )

    def test_init_error_with_non_compatible_dependency_manager(self):
        with self.assertRaises(GenerateProjectFailedError) as ctx:
            generate_project(
                location=self.location,
                runtime=self.runtime,
                package_type=ZIP,
                dependency_manager="gradle",
                output_dir=self.output_dir,
                name=self.name,
                no_input=self.no_input,
            )
        self.assertEqual(
            "An error occurred while generating this project "
            "testing project: Lambda Runtime python3.6 "
            "does not support dependency manager: gradle",
            str(ctx.exception),
        )

    @patch("samcli.lib.init.cookiecutter")
    def test_when_generate_project_returns_error(self, cookiecutter_patch):

        # GIVEN generate_project fails to create a project
        ex = CookiecutterException("something is wrong")
        cookiecutter_patch.side_effect = ex

        expected_msg = str(GenerateProjectFailedError(project=self.name, provider_error=ex))

        # WHEN generate_project returns an error
        # THEN we should receive a GenerateProjectFailedError Exception
        with self.assertRaises(GenerateProjectFailedError) as ctx:
            generate_project(
                location=self.location,
                runtime=self.runtime,
                package_type=ZIP,
                dependency_manager=self.dependency_manager,
                output_dir=self.output_dir,
                name=self.name,
                no_input=self.no_input,
            )

        self.assertEqual(expected_msg, str(ctx.exception))

    @patch("samcli.lib.init.cookiecutter")
    def test_must_set_cookiecutter_context_when_location_and_extra_context_is_provided(self, cookiecutter_patch):
        cookiecutter_context = {"key1": "value1", "key2": "value2"}
        custom_location = "mylocation"
        generate_project(
            location=custom_location, output_dir=self.output_dir, no_input=False, extra_context=cookiecutter_context
        )

        # THEN we should receive no errors
        cookiecutter_patch.assert_called_once_with(
            extra_context=cookiecutter_context, template=custom_location, no_input=False, output_dir=self.output_dir
        )

    @patch("samcli.lib.init.cookiecutter")
    def test_must_set_cookiecutter_context_when_app_template_is_provided(self, cookiecutter_patch):
        cookiecutter_context = {"key1": "value1", "key2": "value2"}
        generate_project(
            runtime=self.runtime,
            package_type=ZIP,
            dependency_manager=self.dependency_manager,
            output_dir=self.output_dir,
            name=self.name,
            no_input=self.no_input,
            extra_context=cookiecutter_context,
        )

        # THEN we should receive no errors
        cookiecutter_patch.assert_called_once_with(
            extra_context=cookiecutter_context,
            no_input=self.no_input,
            output_dir=self.output_dir,
            template=self.template,
        )

    @patch("samcli.lib.init.cookiecutter")
    @patch("samcli.lib.init.generate_non_cookiecutter_project")
    def test_init_arbitrary_project_with_location_is_not_cookiecutter(
        self, generate_non_cookiecutter_project_mock, cookiecutter_mock
    ):

        cookiecutter_mock.side_effect = RepositoryNotFound("msg")

        generate_project(location=self.location, output_dir=self.output_dir)

        generate_non_cookiecutter_project_mock.assert_called_with(location=self.location, output_dir=self.output_dir)

    @patch("samcli.lib.init.cookiecutter")
    @patch("samcli.lib.init.generate_non_cookiecutter_project")
    def test_init_arbitrary_project_with_named_folder(self, generate_non_cookiecutter_project_mock, cookiecutter_mock):

        cookiecutter_mock.side_effect = RepositoryNotFound("msg")

        generate_project(location=self.location, output_dir=self.output_dir, name=self.name)

        expected_output_dir = str(Path(self.output_dir, self.name))
        generate_non_cookiecutter_project_mock.assert_called_with(
            location=self.location, output_dir=expected_output_dir
        )

    @parameterized.expand(["https://example.com", "https://nonexist-domain.com"])
    def test_when_generate_project_with_invalid_template_location(self, invalid_location):
        expected_msg = str(InvalidLocationError(template=invalid_location))

        # WHEN the --location is not valid
        # THEN we should receive a InvalidLocationError Exception
        with self.assertRaises(InvalidLocationError) as ctx:
            generate_project(
                location=invalid_location,
                runtime=self.runtime,
                package_type=ZIP,
                dependency_manager=self.dependency_manager,
                output_dir=self.output_dir,
                name=self.name,
                no_input=self.no_input,
            )

        self.assertEqual(expected_msg, str(ctx.exception))
