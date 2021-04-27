from unittest import TestCase
from unittest.mock import patch, Mock, ANY
import os
from pathlib import Path
from samcli.commands.pipeline.init.interactive_init_flow import (
    do_interactive,
    PipelineTemplateCloneException,
    APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME,
    shared_path,
    CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME,
)
from samcli.commands.pipeline.init.pipeline_templates_manifest import AppPipelineTemplateManifestException
from samcli.lib.utils.git_repo import CloneRepoException
from samcli.lib.cookiecutter.interactive_flow_creator import QuestionsNotFoundException


class TestInteractiveInitFlow(TestCase):
    @patch("samcli.commands.pipeline.init.interactive_init_flow._read_app_pipeline_templates_manifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow._select_pipeline_template")
    @patch("samcli.commands.pipeline.init.interactive_init_flow._generate_from_pipeline_template")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.shared_path")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    def test_app_pipeline_templates_clone_fail_when_an_old_clone_exists(
        self,
        click_mock,
        clone_mock,
        shared_path_mock,
        generate_from_pipeline_template_mock,
        select_pipeline_template_mock,
        read_app_pipeline_templates_manifest_mock,
    ):
        # setup
        clone_mock.side_effect = CloneRepoException  # clone fail
        app_pipeline_templates_path_mock = Mock()
        selected_pipeline_template_path_mock = Mock()
        pipeline_templates_manifest_mock = Mock()
        shared_path_mock.joinpath.return_value = app_pipeline_templates_path_mock
        app_pipeline_templates_path_mock.exists.return_value = True  # An old clone exists
        app_pipeline_templates_path_mock.joinpath.return_value = selected_pipeline_template_path_mock
        read_app_pipeline_templates_manifest_mock.return_value = pipeline_templates_manifest_mock
        click_mock.prompt.return_value = "1"  # App pipeline templates

        # trigger
        do_interactive()

        # verify
        clone_mock.assert_called_once_with(
            clone_dir=shared_path_mock, clone_name=APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME, replace_existing=True
        )
        app_pipeline_templates_path_mock.exists.assert_called_once()
        read_app_pipeline_templates_manifest_mock.assert_called_once_with(
            pipeline_templates_dir=app_pipeline_templates_path_mock
        )
        select_pipeline_template_mock.assert_called_once_with(
            pipeline_templates_manifest=pipeline_templates_manifest_mock
        )
        generate_from_pipeline_template_mock.assert_called_once_with(
            pipeline_template_dir=selected_pipeline_template_path_mock
        )

    @patch("samcli.commands.pipeline.init.interactive_init_flow.shared_path")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    def test_app_pipeline_templates_clone_fail_when_no_old_clone_exist(self, click_mock, clone_mock, shared_path_mock):
        # setup
        clone_mock.side_effect = CloneRepoException  # clone fail
        app_pipeline_templates_path_mock = Mock()
        shared_path_mock.joinpath.return_value = app_pipeline_templates_path_mock
        app_pipeline_templates_path_mock.exists.return_value = False  # No old clone exists
        click_mock.prompt.return_value = "1"  # App pipeline templates

        # trigger
        with self.assertRaises(PipelineTemplateCloneException):
            do_interactive()

    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    def test_custom_pipeline_template_clone_fail(self, click_mock, clone_mock):
        # setup
        clone_mock.side_effect = CloneRepoException  # clone fail
        click_mock.prompt.side_effect = [
            "2",  # Custom pipeline templates
            "https://github.com/any-custom-pipeline-template-repo.git",  # Custom pipeline template repo URL
        ]

        # trigger
        with self.assertRaises(PipelineTemplateCloneException):
            do_interactive()

    @patch("samcli.commands.pipeline.init.interactive_init_flow._read_app_pipeline_templates_manifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    def test_app_pipeline_templates_with_invalid_manifest(
        self, click_mock, clone_mock, read_app_pipeline_templates_manifest_mock
    ):
        # setup
        app_pipeline_templates_path_mock = Mock()
        clone_mock.return_value = app_pipeline_templates_path_mock
        read_app_pipeline_templates_manifest_mock.side_effect = AppPipelineTemplateManifestException("")
        click_mock.prompt.return_value = "1"  # App pipeline templates

        # trigger
        with self.assertRaises(AppPipelineTemplateManifestException):
            do_interactive()

    @patch("samcli.commands.pipeline.init.interactive_init_flow.shutil")
    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.InteractiveFlowCreator.create_flow")
    @patch("samcli.commands.pipeline.init.interactive_init_flow._read_app_pipeline_templates_manifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    def test_generate_pipeline_configuration_file_from_app_pipeline_template_happy_case(
        self,
        click_mock,
        clone_mock,
        read_app_pipeline_templates_manifest_mock,
        create_interactive_flow_mock,
        cookiecutter_mock,
        shutil_mock,
    ):
        # setup
        any_app_pipeline_templates_path = Path(
            os.path.normpath(shared_path.joinpath(APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME))
        )
        clone_mock.return_value = any_app_pipeline_templates_path
        jenkins_template_location = "some/location"
        jenkins_template_mock = Mock(
            name="Jenkins pipeline template", location=jenkins_template_location, provider="Jenkins"
        )
        pipeline_templates_manifest_mock = Mock(providers=["Gitlab", "Jenkins"], templates=[jenkins_template_mock])
        read_app_pipeline_templates_manifest_mock.return_value = pipeline_templates_manifest_mock
        interactive_flow_mock = Mock()
        create_interactive_flow_mock.return_value = interactive_flow_mock
        cookiecutter_context_mock = Mock()
        interactive_flow_mock.run.return_value = cookiecutter_context_mock

        click_mock.prompt.side_effect = [
            "1",  # App pipeline templates
            "2",  # choose "Jenkins" when prompt for CI/CD provider. (See pipeline_templates_manifest_mock, Jenkins is the 2nd provider)
            "1",  # choose "Jenkins pipeline template" when prompt for pipeline template
        ]

        # trigger
        do_interactive()

        # verify
        expected_cookicutter_template_location = any_app_pipeline_templates_path.joinpath(jenkins_template_location)
        clone_mock.assert_called_once_with(
            clone_dir=shared_path, clone_name=APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME, replace_existing=True
        )
        read_app_pipeline_templates_manifest_mock.assert_called_once_with(
            pipeline_templates_dir=any_app_pipeline_templates_path
        )
        create_interactive_flow_mock.assert_called_once_with(
            flow_definition_path=str(expected_cookicutter_template_location.joinpath("questions.json"))
        )
        interactive_flow_mock.run.assert_called_once()
        cookiecutter_mock.assert_called_once_with(
            template=str(expected_cookicutter_template_location),
            output_dir=".",
            no_input=True,
            extra_context=cookiecutter_context_mock,
        )
        shutil_mock.rm_tree.assert_not_called()

    @patch("samcli.commands.pipeline.init.interactive_init_flow._read_app_pipeline_templates_manifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    def test_generate_pipeline_configuration_file_when_pipeline_template_missing_questions_file(
        self, click_mock, clone_mock, read_app_pipeline_templates_manifest_mock
    ):
        # setup
        any_app_pipeline_templates_path = Path(
            os.path.normpath(shared_path.joinpath(APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME))
        )
        clone_mock.return_value = any_app_pipeline_templates_path
        jenkins_template_location = "some/location"
        jenkins_template_mock = Mock(
            name="Jenkins pipeline template", location=jenkins_template_location, provider="Jenkins"
        )
        pipeline_templates_manifest_mock = Mock(providers=["Gitlab", "Jenkins"], templates=[jenkins_template_mock])
        read_app_pipeline_templates_manifest_mock.return_value = pipeline_templates_manifest_mock

        click_mock.prompt.side_effect = [
            "1",  # App pipeline templates
            "2",  # choose "Jenkins" when prompt for CI/CD provider. (See pipeline_templates_manifest_mock, Jenkins is the 2nd provider)
            "1",  # choose "Jenkins pipeline template" when prompt for pipeline template
        ]

        # trigger
        with self.assertRaises(QuestionsNotFoundException):
            do_interactive()

    @patch("samcli.commands.pipeline.init.interactive_init_flow.shutil")
    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.InteractiveFlowCreator.create_flow")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    def test_generate_pipeline_configuration_file_from_custom_pipeline_template_happy_case(
        self, click_mock, clone_mock, create_interactive_flow_mock, cookiecutter_mock, shutil_mock
    ):
        # setup
        any_custom_pipeline_templates_path = Path(
            os.path.normpath(shared_path.joinpath(CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME))
        )
        clone_mock.return_value = any_custom_pipeline_templates_path
        interactive_flow_mock = Mock()
        create_interactive_flow_mock.return_value = interactive_flow_mock
        cookiecutter_context_mock = Mock()
        interactive_flow_mock.run.return_value = cookiecutter_context_mock

        click_mock.prompt.side_effect = [
            "2",  # Custom pipeline templates
            "https://github.com/any-custom-pipeline-template-repo.git",  # Custom pipeline template repo URL
        ]

        # trigger
        do_interactive()

        # verify
        clone_mock.assert_called_once_with(
            clone_dir=shared_path, clone_name=CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME, replace_existing=True
        )
        create_interactive_flow_mock.assert_called_once_with(
            flow_definition_path=str(any_custom_pipeline_templates_path.joinpath("questions.json"))
        )
        interactive_flow_mock.run.assert_called_once()
        cookiecutter_mock.assert_called_once_with(
            template=str(any_custom_pipeline_templates_path),
            output_dir=".",
            no_input=True,
            extra_context=cookiecutter_context_mock,
        )
        shutil_mock.rmtree.assert_called_once_with(any_custom_pipeline_templates_path, onerror=ANY)
