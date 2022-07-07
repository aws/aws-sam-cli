from unittest import TestCase
from unittest.mock import Mock, patch
from collections import namedtuple

from samcli.commands.exceptions import UserException
from samcli.commands.local.cli_common.user_exceptions import SamTemplateNotFoundException, InvalidSamTemplateException
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.commands.validate.validate import _read_sam_file
from samcli.commands.transform.transform import do_cli

ctx_mock = namedtuple("ctx", ["profile", "region"])


class TestTransformCli(TestCase):
    # Testing if the path to the file is not valid
    @patch("samcli.commands.transform.transform.click")
    @patch("samcli.commands.validate.validate.os.path.exists")
    def test_file_missing(self, path_exists_patch, click_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = False

        with self.assertRaises(SamTemplateNotFoundException):
            _read_sam_file(template_path)

    @patch("samcli.yamlhelper.yaml_parse")
    @patch("samcli.commands.validate.validate.click")
    @patch("samcli.commands.validate.validate.os.path.exists")
    def test_file_parsed(self, path_exists_patch, click_patch, yaml_parse_patch):
        template_path = "path_to_template"

        path_exists_patch.return_value = True

        yaml_parse_patch.return_value = {"a": "b"}

        actual_template = _read_sam_file(template_path)

        self.assertEqual(actual_template, {"a": "b"})
        