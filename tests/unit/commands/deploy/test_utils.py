from unittest import TestCase
from unittest.mock import patch

from samcli.commands.deploy.utils import hide_noecho_parameter_overrides, print_deploy_args, sanitize_parameter_overrides


class TestDeployUtils(TestCase):
    @patch("samcli.commands.deploy.utils.click.secho")
    @patch("samcli.commands.deploy.utils.click.echo")
    def test_print_deploy_args_prints_parallel_upload_and_optional_sections(self, echo_mock, secho_mock):
        print_deploy_args(
            stack_name="stack",
            s3_bucket="bucket",
            image_repository={"MyFunc": "123.dkr.ecr.us-east-1.amazonaws.com/repo"},
            region="us-east-1",
            capabilities=["CAPABILITY_IAM"],
            parameter_overrides={"Param": "Value"},
            confirm_changeset=False,
            signing_profiles={"MyFunc": {"profile_name": "pname", "profile_owner": "powner"}},
            use_changeset=True,
            disable_rollback=False,
            parallel_upload=True,
        )

        echo_texts = [call.args[0] for call in echo_mock.call_args_list]
        self.assertTrue(any("Parallel uploads" in text for text in echo_texts))
        self.assertTrue(any("Confirm changeset" in text for text in echo_texts))
        self.assertTrue(any("Deployment image repository" in text for text in echo_texts))

        # Basic smoke check that we printed the header/footer sections.
        self.assertGreaterEqual(secho_mock.call_count, 2)

    @patch("samcli.commands.deploy.utils.click.secho")
    @patch("samcli.commands.deploy.utils.click.echo")
    def test_print_deploy_args_without_optional_sections(self, echo_mock, secho_mock):
        print_deploy_args(
            stack_name="stack",
            s3_bucket="bucket",
            image_repository=None,
            region="us-east-1",
            capabilities=["CAPABILITY_IAM"],
            parameter_overrides={"Param": "Value"},
            confirm_changeset=False,
            signing_profiles=None,
            use_changeset=False,
            disable_rollback=False,
            parallel_upload=False,
        )

        echo_texts = [call.args[0] for call in echo_mock.call_args_list]
        self.assertFalse(any("Confirm changeset" in text for text in echo_texts))
        self.assertFalse(any("Deployment image repository" in text for text in echo_texts))

    def test_sanitize_parameter_overrides(self):
        self.assertEqual(
            {"A": "1", "B": "2"},
            sanitize_parameter_overrides({"A": {"Value": "1"}, "B": "2"}),
        )

    def test_hide_noecho_parameter_overrides(self):
        template_parameters = {"Parameters": {"Secret": {"NoEcho": True}, "Visible": {"NoEcho": False}}}
        overrides = {"Secret": "shh", "Visible": "ok"}
        self.assertEqual(
            {"Secret": "*" * 5, "Visible": "ok"},
            hide_noecho_parameter_overrides(template_parameters, overrides),
        )
