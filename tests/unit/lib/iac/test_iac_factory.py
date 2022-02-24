from unittest import TestCase
from unittest.mock import patch, MagicMock

from samcli.lib.iac.cdk.cdk_iac import CdkIacImplementation
from samcli.lib.iac.exceptions import InvalidIaCPluginException, InvalidProjectTypeException
from samcli.lib.iac.cfn.cfn_iac import CfnIacImplementation
from samcli.lib.iac.iac_factory import IaCFactory
from samcli.lib.iac.plugins_interfaces import SamCliContext, ProjectTypes


class TestGetIaC(TestCase):
    def test_get_cfn_impl(self):
        context_map = {"project_type": "CFN", "template_file": "input-template-file"}
        context = SamCliContext(
            command_options_map=context_map,
            sam_command_name="",
            is_guided=False,
            is_debugging=False,
            profile={},
            region="",
        )
        iac_factory = IaCFactory(context)
        iac_implementation = iac_factory.get_iac()
        self.assertIsInstance(iac_implementation, CfnIacImplementation)

    def test_get_cdk_impl(self):
        context_map = {"project_type": "CDK"}
        context = SamCliContext(
            command_options_map=context_map,
            sam_command_name="",
            is_guided=False,
            is_debugging=False,
            profile={},
            region="",
        )
        iac_factory = IaCFactory(context)
        iac_implementation = iac_factory.get_iac()
        self.assertIsInstance(iac_implementation, CdkIacImplementation)

    def test_no_project_type_found(self):
        expected_message = "Project type not found in sam-cli command options"
        context_map = {}
        context = SamCliContext(
            command_options_map=context_map,
            sam_command_name="",
            is_guided=False,
            is_debugging=False,
            profile={},
            region="",
        )
        iac_factory = IaCFactory(context)
        with self.assertRaises(ValueError) as ctx:
            iac_factory.get_iac()
        self.assertEqual(str(ctx.exception), expected_message)

    def test_invalid_project_type(self):
        expected_message = (
            f"ABC is an invalid project type option value, the value should be one "
            f"of the following {[ptype.value for ptype in ProjectTypes]} "
        )
        context_map = {"project_type": "ABC"}
        context = SamCliContext(
            command_options_map=context_map,
            sam_command_name="",
            is_guided=False,
            is_debugging=False,
            profile={},
            region="",
        )
        iac_factory = IaCFactory(context)
        with self.assertRaises(InvalidProjectTypeException) as ctx:
            iac_factory.get_iac()
        self.assertEqual(str(ctx.exception), expected_message)


class TestDetectProjectType(TestCase):
    @patch("samcli.lib.iac.iac_factory.os")
    def test_detect_cfn_project_type(self, mock_os):
        mock_os.listdir.return_value = ["template.yaml", "__init__.py", "hello_world", ".aws-sam"]
        project = IaCFactory.detect_project_type("/project/path/dir")
        self.assertEqual("CFN", project)

    @patch("samcli.lib.iac.iac_factory.os")
    def test_detect_cdk_project_type(self, mock_os):
        mock_os.listdir.return_value = ["cdk.json", "__init__.py", "hello_world", "cdk.out"]
        project = IaCFactory.detect_project_type("/project/path/dir")
        self.assertEqual("CDK", project)

    @patch("samcli.lib.iac.iac_factory.os")
    @patch.object(CfnIacImplementation, "get_iac_file_patterns", MagicMock(return_value=(["*.yaml"])))
    def test_detect_cfn_project_using_pattern(self, mock_os):
        mock_os.listdir.return_value = ["template.yaml", "__init__.py", "hello_world", ".aws-sam"]
        project = IaCFactory.detect_project_type("/project/path/dir")
        self.assertEqual("CFN", project)

    @patch("samcli.lib.iac.iac_factory.os")
    def test_detect_cfn_project_type_multiple_matched_files(self, mock_os):
        mock_os.listdir.return_value = ["template.yaml", "template.yml", "__init__.py", "hello_world", ".aws-sam"]
        project = IaCFactory.detect_project_type("/project/path/dir")
        self.assertEqual("CFN", project)

    @patch("samcli.lib.iac.iac_factory.os")
    def test_detect_multiple_project_types(self, mock_os):
        expected_message = (
            "Could not determine the plugin type from the provided files:\n\n"
            "cdk.json, template.yaml, __init__.py, hello_world, cdk.out"
        )
        mock_os.listdir.return_value = ["cdk.json", "template.yaml", "__init__.py", "hello_world", "cdk.out"]
        with self.assertRaises(InvalidIaCPluginException) as ctx:
            IaCFactory.detect_project_type("/project/path/dir")
        self.assertEqual(str(ctx.exception), expected_message)

    @patch("samcli.lib.iac.iac_factory.os")
    def test_detect_no_valid_project_types(self, mock_os):
        expected_message = (
            "Could not determine the plugin type from the provided files:\n\n" "__init__.py, hello_world, cdk.out"
        )
        mock_os.listdir.return_value = ["__init__.py", "hello_world", "cdk.out"]
        with self.assertRaises(InvalidIaCPluginException) as ctx:
            IaCFactory.detect_project_type("/project/path/dir")
        self.assertEqual(str(ctx.exception), expected_message)
