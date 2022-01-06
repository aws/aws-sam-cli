from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.commands._utils.template import get_template_data
from samcli.lib.iac.cdk.utils import is_cdk_project


class TestIsCDKProject(TestCase):
    @parameterized.expand(
        [
            (True, "cdk_template_metadata_path.yaml"),
            (True, "resource_metadata.yaml"),
            (True, "resource_and_path_metadata.yaml"),
            (False, "non_cdk_cfn.yaml"),
        ]
    )
    def test_cfn_templates(self, expected_is_cdk, template_name):
        template_path = Path(__file__).resolve().parents[0].joinpath("test_data", template_name)
        template = get_template_data(str(template_path))
        is_cdk = is_cdk_project(template)
        self.assertEqual(is_cdk, expected_is_cdk)

    @parameterized.expand(
        [
            (True, ["lib", "app.py", "requirements.txt", "cdk.json"]),
            (True, ["Stack.template.json", "manifest.json", "asset"]),
            (True, ["Stack.template.json", "tree.json", "asset"]),
            (True, ["Stack.template.json", "manifest.json", "tree.json"]),
            (False, ["lib", "app.py", "requirements.txt"]),
            (False, []),
        ]
    )
    def test_cdk_project_files(self, expected_is_cdk, project_files):
        with patch("samcli.lib.iac.cdk.utils.os") as mock_os:
            mock_os.listdir.return_value = project_files
            is_cdk = is_cdk_project({})
            self.assertEqual(is_cdk, expected_is_cdk)
