#
# class TestProjectTypeCallback(TestCase):
#     @patch("samcli.commands._utils.options.determine_project_type")
#     def test_raise_error_if_detected_not_match_inputted(self, determine_project_type_mock):
#         context_mock = MockContext(info_name="test", parent=None, params=Mock())
#         param_mock = Mock()
#         param_mock.name = "--project-type"
#         provided_value = "CDK"
#         detected_value = "CFN"
#         include_build = True
#         determine_project_type_mock.return_value = detected_value
#         with self.assertRaises(click.BadOptionUsage) as ex:
#             project_type_callback(context_mock, param_mock, provided_value, include_build)
#         self.assertEqual(ex.exception.option_name, param_mock.name)
#         self.assertEqual(
#             ex.exception.message, "It seems your project type is CFN. However, you specified CDK in --project-type"
#         )
#
#     @patch("samcli.commands._utils.options.determine_project_type")
#     def test_return_detected_project_type(self, determine_project_type_mock):
#         context_mock = MockContext(info_name="test", parent=None, params=Mock())
#         param_mock = Mock()
#         param_mock.name = "--project-type"
#         detected_value = "CFN"
#         include_build = True
#         determine_project_type_mock.return_value = detected_value
#         self.assertEqual(project_type_callback(context_mock, param_mock, None, include_build), detected_value)
#
#     @patch("samcli.commands._utils.options.determine_project_type")
#     def test_return_provided_project_type(self, determine_project_type_mock):
#         context_mock = MockContext(info_name="test", parent=None, params=Mock())
#         param_mock = Mock()
#         param_mock.name = "--project-type"
#         detected_value = "CFN"
#         provided_value = "CFN"
#         include_build = True
#         determine_project_type_mock.return_value = detected_value
#         self.assertEqual(project_type_callback(context_mock, param_mock, provided_value, include_build), provided_value)
#
#
# class TestDetermineProjectType(TestCase):
#     @patch("samcli.commands._utils.options.find_cfn_template")
#     @patch("samcli.commands._utils.options.find_cdk_file")
#     def test_return_cfn_type(self, find_cdk_file_mock, find_cfn_template_mock):
#         find_cfn_template_mock.return_value = True
#         find_cdk_file_mock.return_value = False
#         self.assertEqual(determine_project_type(True), "CFN")
#
#     @patch("samcli.commands._utils.options.find_cfn_template")
#     @patch("samcli.commands._utils.options.find_cdk_file")
#     def test_return_cdk_type(self, find_cdk_file_mock, find_cfn_template_mock):
#         find_cfn_template_mock.return_value = False
#         find_cdk_file_mock.return_value = True
#         self.assertEqual(determine_project_type(True), "CDK")
#
#     @patch("samcli.commands._utils.options.find_cfn_template")
#     @patch("samcli.commands._utils.options.find_cdk_file")
#     def test_return_default(self, find_cdk_file_mock, find_cfn_template_mock):
#         find_cfn_template_mock.return_value = False
#         find_cdk_file_mock.return_value = False
#         self.assertEqual(determine_project_type(True), "CFN")
#
