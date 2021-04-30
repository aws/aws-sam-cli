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
    @patch("samcli.commands.pipeline.init.interactive_init_flow._prompt_pipeline_template")
    @patch("samcli.commands.pipeline.init.interactive_init_flow._generate_from_pipeline_template")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.shared_path")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.lib.cookiecutter.question.click")
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
            shared_path_mock, APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME, replace_existing=True
        )
        app_pipeline_templates_path_mock.exists.assert_called_once()
        read_app_pipeline_templates_manifest_mock.assert_called_once_with(app_pipeline_templates_path_mock)
        select_pipeline_template_mock.assert_called_once_with(pipeline_templates_manifest_mock)
        generate_from_pipeline_template_mock.assert_called_once_with(selected_pipeline_template_path_mock)

    @patch("samcli.commands.pipeline.init.interactive_init_flow.shared_path")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.lib.cookiecutter.question.click")
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
    @patch("samcli.lib.cookiecutter.question.click")
    def test_custom_pipeline_template_clone_fail(self, question_click_mock, init_click_mock, clone_mock):
        # setup
        clone_mock.side_effect = CloneRepoException  # clone fail
        question_click_mock.prompt.return_value = "2"  # Custom pipeline templates
        init_click_mock.prompt.return_value = (
            "https://github.com/any-custom-pipeline-template-repo.git"  # Custom pipeline template repo URL
        )

        # trigger
        with self.assertRaises(PipelineTemplateCloneException):
            do_interactive()

    @patch("samcli.commands.pipeline.init.interactive_init_flow._read_app_pipeline_templates_manifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.lib.cookiecutter.question.click")
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

    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.InteractiveFlowCreator.create_flow")
    @patch("samcli.commands.pipeline.init.interactive_init_flow._read_app_pipeline_templates_manifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_generate_pipeline_configuration_file_from_app_pipeline_template_happy_case(
        self,
        click_mock,
        clone_mock,
        read_app_pipeline_templates_manifest_mock,
        create_interactive_flow_mock,
        cookiecutter_mock,
    ):
        # setup
        any_app_pipeline_templates_path = Path(
            os.path.normpath(shared_path.joinpath(APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME))
        )
        clone_mock.return_value = any_app_pipeline_templates_path
        jenkins_template_location = "some/location"
        jenkins_template_mock = Mock(
            display_name="Jenkins pipeline template", location=jenkins_template_location, provider="jenkins"
        )
        pipeline_templates_manifest_mock = Mock(
            providers=[
                Mock(id="gitlab", display_name="Gitlab"),
                Mock(id="jenkins", display_name="Jenkins"),
            ],
            templates=[jenkins_template_mock],
        )
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
        clone_mock.assert_called_once_with(shared_path, APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME, replace_existing=True)
        read_app_pipeline_templates_manifest_mock.assert_called_once_with(any_app_pipeline_templates_path)
        create_interactive_flow_mock.assert_called_once_with(
            str(expected_cookicutter_template_location.joinpath("questions.json"))
        )
        interactive_flow_mock.run.assert_called_once()
        cookiecutter_mock.assert_called_once_with(
            template=str(expected_cookicutter_template_location),
            output_dir=".",
            no_input=True,
            extra_context=cookiecutter_context_mock,
        )

    @patch("samcli.commands.pipeline.init.interactive_init_flow._read_app_pipeline_templates_manifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_generate_pipeline_configuration_file_when_pipeline_template_missing_questions_file(
        self, click_mock, clone_mock, read_app_pipeline_templates_manifest_mock
    ):
        # setup
        any_app_pipeline_templates_path = shared_path.joinpath(APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME)
        clone_mock.return_value = any_app_pipeline_templates_path
        jenkins_template_location = "some/location"
        jenkins_template_mock = Mock(
            display_name="Jenkins pipeline template", location=jenkins_template_location, provider="jenkins"
        )
        pipeline_templates_manifest_mock = Mock(
            providers=[
                Mock(id="gitlab", display_name="Gitlab"),
                Mock(id="jenkins", display_name="Jenkins"),
            ],
            templates=[jenkins_template_mock],
        )
        read_app_pipeline_templates_manifest_mock.return_value = pipeline_templates_manifest_mock

        click_mock.prompt.side_effect = [
            "1",  # App pipeline templates
            "2",  # choose "Jenkins" when prompt for CI/CD provider. (See pipeline_templates_manifest_mock, Jenkins is the 2nd provider)
            "1",  # choose "Jenkins pipeline template" when prompt for pipeline template
        ]

        # trigger
        with self.assertRaises(QuestionsNotFoundException):
            do_interactive()

    @patch("samcli.commands.pipeline.init.interactive_init_flow.os")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.osutils")
    @patch("samcli.commands.pipeline.init.interactive_init_flow._generate_from_pipeline_template")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_generate_pipeline_configuration_file_from_custom_local_existing_path_will_not_do_git_clone(
        self,
        questions_click_mock,
        init_click_mock,
        clone_mock,
        generate_from_pipeline_template_mock,
        osutils_mock,
        os_mock,
    ):
        # setup
        local_pipeline_templates_path = "/any/existing/local/path"
        os_mock.path.exists.return_value = True
        questions_click_mock.prompt.return_value = "2"  # Custom pipeline templates
        init_click_mock.prompt.return_value = local_pipeline_templates_path  # git repo path
        # trigger
        do_interactive()

        # verify
        osutils_mock.mkdir_temp.assert_not_called()
        clone_mock.assert_not_called()
        generate_from_pipeline_template_mock.assert_called_once_with(Path(local_pipeline_templates_path))

    @patch("samcli.commands.pipeline.init.interactive_init_flow.osutils")
    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.InteractiveFlowCreator.create_flow")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.click")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_generate_pipeline_configuration_file_from_custom_remote_pipeline_template_happy_case(
        self,
        questions_click_mock,
        init_click_mock,
        clone_mock,
        create_interactive_flow_mock,
        cookiecutter_mock,
        osutils_mock,
    ):
        # setup
        any_temp_dir = "/tmp/any/dir"
        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=any_temp_dir)
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()
        any_custom_pipeline_templates_path = Path(os.path.join(any_temp_dir, CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME))
        clone_mock.return_value = any_custom_pipeline_templates_path
        interactive_flow_mock = Mock()
        create_interactive_flow_mock.return_value = interactive_flow_mock
        cookiecutter_context_mock = Mock()
        interactive_flow_mock.run.return_value = cookiecutter_context_mock

        questions_click_mock.prompt.return_value = "2"  # Custom pipeline templates
        init_click_mock.prompt.return_value = "https://github.com/any-custom-pipeline-template-repo.git"

        # trigger
        do_interactive()

        # verify
        osutils_mock.mkdir_temp.assert_called_once()  # Custom templates are cloned to temp
        clone_mock.assert_called_once_with(
            Path(any_temp_dir), CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME, replace_existing=True
        )
        create_interactive_flow_mock.assert_called_once_with(
            str(any_custom_pipeline_templates_path.joinpath("questions.json"))
        )
        interactive_flow_mock.run.assert_called_once()
        cookiecutter_mock.assert_called_once_with(
            template=str(any_custom_pipeline_templates_path),
            output_dir=".",
            no_input=True,
            extra_context=cookiecutter_context_mock,
        )
