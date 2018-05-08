from unittest import TestCase
from mock import patch

from cookiecutter.exceptions import CookiecutterException
from samcli.local.init import generate_project
from samcli.local.init import GenerateProjectFailedError
from samcli.local.init import RUNTIME_TEMPLATE_MAPPING


class TestInit(TestCase):

    def setUp(self):
        self.location = None
        self.runtime = "python3.6"
        self.output_dir = "."
        self.name = "testing project"
        self.no_input = True
        self.extra_context = {'project_name': 'testing project', "runtime": self.runtime}
        self.template = RUNTIME_TEMPLATE_MAPPING[self.runtime]

    @patch("samcli.local.init.cookiecutter")
    def test_init_successful(self, cookiecutter_patch):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        generate_project(
            location=self.location, runtime=self.runtime, output_dir=self.output_dir,
            name=self.name, no_input=self.no_input)

        # THEN we should receive no errors
        cookiecutter_patch.assert_called_once_with(
                extra_context=self.extra_context, no_input=self.no_input,
                output_dir=self.output_dir, template=self.template)

    @patch("samcli.local.init.cookiecutter")
    def test_when_generate_project_returns_error(self, cookiecutter_patch):

        # GIVEN generate_project fails to create a project
        ex = CookiecutterException("something is wrong")
        cookiecutter_patch.side_effect = ex

        expected_msg = str(GenerateProjectFailedError(project=self.name, provider_error=ex))

        # WHEN generate_project returns an error
        # THEN we should receive a GenerateProjectFailedError Exception
        with self.assertRaises(GenerateProjectFailedError) as ctx:
            generate_project(
                    location=self.location, runtime=self.runtime,
                    output_dir=self.output_dir, name=self.name, no_input=self.no_input)

        self.assertEquals(expected_msg, str(ctx.exception))

    @patch("samcli.local.init.cookiecutter")
    def test_must_not_set_name_when_location_is_given(self, cookiecutter_patch):
        generate_project(runtime=self.runtime, output_dir=self.output_dir,
                         name=self.name, no_input=False)

        expected_extra_content = {
            "project_name": self.name,
            "runtime": self.runtime
        }
        # THEN we should receive no errors
        cookiecutter_patch.assert_called_once_with(
                template=self.template,
                extra_context=expected_extra_content, no_input=True,
                output_dir=self.output_dir)

    @patch("samcli.local.init.cookiecutter")
    def test_must_not_set_extra_content(self, cookiecutter_patch):
        custom_location = "mylocation"
        generate_project(location=custom_location,
                         runtime=self.runtime, output_dir=self.output_dir,
                         name=self.name, no_input=False)

        # THEN we should receive no errors
        cookiecutter_patch.assert_called_once_with(
                template=custom_location, no_input=False,
                output_dir=self.output_dir)
