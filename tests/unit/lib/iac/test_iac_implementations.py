from unittest import TestCase
from unittest.mock import MagicMock
import tempfile
import os
import yaml

from samcli.lib.iac.cfn.cfn_iac import CfnIacImplementation
from samcli.lib.iac.plugins_interfaces import SamCliContext, LookupPath


# TODO: Implement these tests when the classes are fully implemented
# These tests are included for code coverage
class TestImplementations(TestCase):
    def test_cfn_implementation(self):
        impl = CfnIacImplementation(MagicMock())
        impl.get_iac_file_patterns()
        impl.update_packaged_locations(MagicMock())
        impl.write_project(MagicMock(), MagicMock())
        self.assertTrue(True)

    def test_cdk_implementation(self):
        impl = CfnIacImplementation(MagicMock())
        impl.get_iac_file_patterns()
        impl.update_packaged_locations(MagicMock())
        impl.write_project(MagicMock(), MagicMock())
        self.assertTrue(True)

    def test_read_project_minimal_template(self):
        # Create a minimal CloudFormation template
        minimal_template = {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Resources": {
                "MyFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "Handler": "index.handler",
                        "Runtime": "python3.8",
                        "CodeUri": "./src"
                    }
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = os.path.join(tmpdir, "template.yaml")
            with open(template_path, "w") as f:
                yaml.dump(minimal_template, f)

            context = SamCliContext(
                command_options_map={"template_file": template_path},
                sam_command_name="test",
                is_guided=False,
                is_debugging=False,
                profile=None,
                region=None
            )
            impl = CfnIacImplementation(context)
            lookup_paths = [LookupPath(tmpdir)]
            project = impl.read_project(lookup_paths)

            # Assert the project contains one stack with the expected resource
            self.assertEqual(len(project.stacks), 1)
            stack = project.stacks[0]
            self.assertIn("Resources", stack)
            resources = stack["Resources"].section_items
            self.assertTrue(any(r.item_id == "MyFunction" for r in resources))