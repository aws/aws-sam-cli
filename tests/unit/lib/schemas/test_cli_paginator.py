from unittest import TestCase
from unittest.mock import patch, ANY

from samcli.lib.schemas.cli_paginator import do_paginate_cli
from samcli.lib.schemas.schemas_cli_message_generator import construct_cli_display_message_for_schemas


class TestCliPaginator(TestCase):
    def setUp(self):
        self.pages = {
            0: ["aws.autoscaling.AWSAPICallViaCloudTrail", "aws.autoscaling.EC2InstanceLaunchLifecycleAction"],
            1: ["aws.codebuild.CodeBuildBuildPhaseChange", "aws.codebuild.CodeBuildBuildStateChange"],
            2: ["aws.codedeploy.CodeDeployDeploymentStateChangeNotification", "aws.batch.BatchJobStateChange"],
            3: ["aws.batch.AWSAPICallViaCloudTrail", "aws.codedeploy.CodeDeployInstanceStateChangeNotification"],
        }
        self.items_per_page = 2

    @patch("click.prompt")
    def test_cli_paginator_choice_after_first_page_is_displayed(self, prompt_mock):
        prompt_mock.return_value = 1
        page_to_render = 0
        cli_display_message = construct_cli_display_message_for_schemas(page_to_render + 1)
        cli_response = do_paginate_cli(self.pages, page_to_render, self.items_per_page, True, cli_display_message)
        self.assertEqual(cli_response["choice"], "aws.autoscaling.AWSAPICallViaCloudTrail")
        self.assertEqual(cli_response["page_to_render"], None)
        prompt_mock.assert_called_once_with(
            "Event Schemas [Page 1/many] (Enter N for next page)", show_choices=False, type=ANY
        )

    @patch("click.prompt")
    def test_cli_paginator_choice_after_last_page_is_displayed(self, prompt_mock):
        prompt_mock.return_value = "P"
        page_to_render = 3
        cli_display_message = construct_cli_display_message_for_schemas(page_to_render + 1, page_to_render + 1)
        cli_response = do_paginate_cli(self.pages, page_to_render, self.items_per_page, True, cli_display_message)
        self.assertEqual(cli_response["choice"], None)
        self.assertEqual(cli_response["page_to_render"], 2)
        prompt_mock.assert_called_once_with(
            "Event Schemas [Page 4/4] (Enter P for previous page)", show_choices=False, type=ANY
        )

    @patch("click.prompt")
    def test_cli_paginator_choice_when_user_selects_next_page(self, prompt_mock):
        prompt_mock.return_value = "N"
        page_to_render = 2
        cli_display_message = construct_cli_display_message_for_schemas(page_to_render + 1)
        cli_response = do_paginate_cli(self.pages, 2, self.items_per_page, True, cli_display_message)
        self.assertEqual(cli_response["choice"], None)
        self.assertEqual(cli_response["page_to_render"], 3)
        prompt_mock.assert_called_once_with(
            "Event Schemas [Page 3/many] (Enter N/P for next/previous page)", show_choices=False, type=ANY
        )

    @patch("click.prompt")
    def test_cli_paginator_choice_when_user_selects_previous_page(self, prompt_mock):
        prompt_mock.return_value = "P"
        page_to_render = 2
        cli_display_message = construct_cli_display_message_for_schemas(page_to_render + 1)
        cli_response = do_paginate_cli(self.pages, 2, self.items_per_page, True, cli_display_message)
        self.assertEqual(cli_response["choice"], None)
        self.assertEqual(cli_response["page_to_render"], 1)
        prompt_mock.assert_called_once_with(
            "Event Schemas [Page 3/many] (Enter N/P for next/previous page)", show_choices=False, type=ANY
        )

    @patch("click.prompt")
    def test_cli_paginator_choice_when_user_selects_next_to_last_page(self, prompt_mock):
        prompt_mock.return_value = "N"
        page_to_render = 2
        cli_display_message = construct_cli_display_message_for_schemas(page_to_render + 1)
        cli_response = do_paginate_cli(self.pages, 2, self.items_per_page, False, cli_display_message)
        self.assertEqual(cli_response["choice"], None)
        self.assertEqual(cli_response["page_to_render"], 3)
        prompt_mock.assert_called_once_with(
            "Event Schemas [Page 3/many] (Enter N/P for next/previous page)", show_choices=False, type=ANY
        )

    @patch("click.prompt")
    def test_cli_paginator_when_page_size_is_one(self, prompt_mock):
        prompt_mock.return_value = 2
        page_to_render = 0
        cli_display_message = construct_cli_display_message_for_schemas(page_to_render + 1)
        pages = {0: ["aws.autoscaling.AWSAPICallViaCloudTrail", "aws.autoscaling.EC2InstanceLaunchLifecycleAction"]}
        cli_response = do_paginate_cli(pages, 0, self.items_per_page, True, cli_display_message)
        self.assertEqual(cli_response["choice"], "aws.autoscaling.EC2InstanceLaunchLifecycleAction")
        self.assertEqual(cli_response["page_to_render"], None)
        prompt_mock.assert_called_once_with("Event Schemas", show_choices=False, type=ANY)
