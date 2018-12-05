import os
import random
import tempfile
import shutil
from unittest import TestCase

from samcli.commands.init import do_cli as init_cli


class TestCli(TestCase):

    def setUp(self):
        self.location = None
        self.runtime = "python3.6"
        self.output_dir = tempfile.mkdtemp()
        self.name = "testing project {}".format(random.randint(1, 10))
        self.no_input = False
        self.cookiecutter_dir = tempfile.mkdtemp()
        self.project_folder = os.path.abspath(
            os.path.join(self.output_dir, self.name))
        self.custom_location_folder = os.path.abspath(
            os.path.join(self.output_dir, 'Name of the project'))
        self.extra_context = {}

    def tearDown(self):
        leftover_folders = (self.output_dir, self.cookiecutter_dir)

        for folder in leftover_folders:
            if os.path.isdir(folder):
                shutil.rmtree(folder)

    def test_generate_project(self):
        # GIVEN generate_project successfully created a project
        # WHEN a project name has been passed
        init_cli(
            ctx=None, location=self.location, runtime=self.runtime, output_dir=self.output_dir,
            name=self.name, no_input=self.no_input, extra_context=self.extra_context)

        # THEN we should see a new project created and a successful return
        self.assertTrue(os.path.isdir(self.project_folder))

    def test_custom_location(self):
        # GIVEN generate_project successfuly created a project
        # WHEN a custom template has been passed
        # and we were asked to accept default values provided by the template
        self.location = "https://github.com/aws-samples/cookiecutter-aws-sam-python"

        init_cli(
            ctx=None, location=self.location, runtime=self.runtime, output_dir=self.output_dir,
            name=self.name, no_input=True, extra_context=self.extra_context)

        # THEN we should see a new project created and a successful return
        # and this new folder should be named 'name-of-the-project'
        # which is the default value for this custom template
        self.assertTrue(os.path.isdir(self.output_dir + '/' + self.name))

    def test_custom_location_with_context(self):
        # GIVEN generate_project successfuly created a project
        # WHEN a custom template has been passed
        # and we inject additional context specific to the target template
        self.location = "https://github.com/aws-samples/cookiecutter-aws-sam-python"

        # CLI expects extra context via Key=Value
        self.extra_context = ('project_short_description="A whole new world"',)

        init_cli(
            ctx=None, location=self.location, runtime=self.runtime, output_dir=self.output_dir,
            name=self.name, no_input=True, extra_context=self.extra_context)

        # THEN we should file the new description inserted into the README for this custom template

        readme_file = os.path.abspath(os.path.join(
            self.output_dir,
            self.name,
            'README.md'
        ))

        self.assertTrue(os.path.isfile(readme_file))

        with open(readme_file) as f:
            readme_content = f.readlines()
            readme_content = "".join(readme_content)

        self.assertTrue("A whole new world" in readme_content)
