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
    _prompt_cicd_provider,
    _prompt_provider_pipeline_template,
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

    @patch("samcli.commands.pipeline.init.interactive_init_flow.SamConfig")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.osutils")
    @patch("samcli.lib.cookiecutter.template.cookiecutter")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.InteractiveFlowCreator.create_flow")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.PipelineTemplatesManifest")
    @patch("samcli.commands.pipeline.init.interactive_init_flow.GitRepo.clone")
    @patch("samcli.commands.pipeline.init.interactive_init_flow._copy_dir_contents_to_cwd_fail_on_exist")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_generate_pipeline_configuration_file_from_app_pipeline_template_happy_case(
        self,
        click_mock,
        _copy_dir_contents_to_cwd_fail_on_exist_mock,
        clone_mock,
        PipelineTemplatesManifest_mock,
        create_interactive_flow_mock,
        cookiecutter_mock,
        osutils_mock,
        samconfig_mock,
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
        PipelineTemplatesManifest_mock.return_value = pipeline_templates_manifest_mock
        cookiecutter_output_dir_mock = "/tmp/any/dir2"
        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(return_value=cookiecutter_output_dir_mock)
        interactive_flow_mock = Mock()
        create_interactive_flow_mock.return_value = interactive_flow_mock
        cookiecutter_context_mock = {"key": "value"}
        interactive_flow_mock.run.return_value = cookiecutter_context_mock
        config_file = Mock()
        samconfig_mock.return_value = config_file
        config_file.exists.return_value = True
        config_file.get_env_names.return_value = ["testing", "prod"]
        config_file.get_env_names.return_value = ["testing", "prod"]
        config_file.get_all.return_value = {"pipeline_execution_role": "arn:aws:iam::123456789012:role/execution-role"}

        click_mock.prompt.side_effect = [
            "1",  # App pipeline templates
            "2",  # choose "Jenkins" when prompt for CI/CD system. (See pipeline_templates_manifest_mock, Jenkins is the 2nd provider)
            "1",  # choose "Jenkins pipeline template" when prompt for pipeline template
        ]

        # trigger
        do_interactive()

        # verify
        osutils_mock.mkdir_temp.assert_called()  # cookiecutter project is generated to temp
        expected_cookicutter_template_location = any_app_pipeline_templates_path.joinpath(jenkins_template_location)
        clone_mock.assert_called_once_with(shared_path, APP_PIPELINE_TEMPLATES_REPO_LOCAL_NAME, replace_existing=True)
        PipelineTemplatesManifest_mock.assert_called_once()
        create_interactive_flow_mock.assert_called_once_with(
            str(expected_cookicutter_template_location.joinpath("questions.json"))
        )
        interactive_flow_mock.run.assert_called_once_with(
            {
                str(["testing", "pipeline_execution_role"]): "arn:aws:iam::123456789012:role/execution-role",
                str(["prod", "pipeline_execution_role"]): "arn:aws:iam::123456789012:role/execution-role",
                str(["environment_names_message"]): "Here are the environment names detected "
                f'in {os.path.join(".aws-sam", "pipeline", "pipelineconfig.toml")}:\n\t- testing\n\t- prod',
            }
        )
        cookiecutter_mock.assert_called_once_with(
            template=str(expected_cookicutter_template_location),
            output_dir=cookiecutter_output_dir_mock,
            no_input=True,
            extra_context=cookiecutter_context_mock,
            overwrite_if_exists=True,
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
            "2",  # choose "Jenkins" when prompt for CI/CD system. (See pipeline_templates_manifest_mock, Jenkins is the 2nd provider)
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
    @patch("samcli.commands.pipeline.init.interactive_init_flow._copy_dir_contents_to_cwd_fail_on_exist")
    @patch("samcli.lib.cookiecutter.question.click")
    def test_generate_pipeline_configuration_file_from_custom_remote_pipeline_template_happy_case(
        self,
        questions_click_mock,
        _copy_dir_contents_to_cwd_fail_on_exist_mock,
        init_click_mock,
        clone_mock,
        create_interactive_flow_mock,
        cookiecutter_mock,
        osutils_mock,
    ):
        # setup
        any_temp_dir = "/tmp/any/dir"
        cookiecutter_output_dir_mock = "/tmp/any/dir2"
        osutils_mock.mkdir_temp.return_value.__enter__ = Mock(side_effect=[any_temp_dir, cookiecutter_output_dir_mock])
        osutils_mock.mkdir_temp.return_value.__exit__ = Mock()
        any_custom_pipeline_templates_path = Path(os.path.join(any_temp_dir, CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME))
        clone_mock.return_value = any_custom_pipeline_templates_path
        interactive_flow_mock = Mock()
        create_interactive_flow_mock.return_value = interactive_flow_mock
        cookiecutter_context_mock = {"key": "value"}
        interactive_flow_mock.run.return_value = cookiecutter_context_mock
        _copy_dir_contents_to_cwd_fail_on_exist_mock.return_value = ["file1"]

        questions_click_mock.prompt.return_value = "2"  # Custom pipeline templates
        init_click_mock.prompt.return_value = "https://github.com/any-custom-pipeline-template-repo.git"

        # trigger
        do_interactive()

        # verify
        # Custom templates are cloned to temp; cookiecutter project is generated to temp
        osutils_mock.mkdir_temp.assert_called()
        clone_mock.assert_called_once_with(
            Path(any_temp_dir), CUSTOM_PIPELINE_TEMPLATE_REPO_LOCAL_NAME, replace_existing=True
        )
        create_interactive_flow_mock.assert_called_once_with(
            str(any_custom_pipeline_templates_path.joinpath("questions.json"))
        )
        interactive_flow_mock.run.assert_called_once()
        cookiecutter_mock.assert_called_once_with(
            template=str(any_custom_pipeline_templates_path),
            output_dir=cookiecutter_output_dir_mock,
            no_input=True,
            extra_context=cookiecutter_context_mock,
            overwrite_if_exists=True,
        )

    @patch("samcli.lib.cookiecutter.question.click")
    def test_prompt_cicd_provider_will_not_prompt_if_the_list_of_providers_has_only_one_provider(self, click_mock):
        gitlab_provider = Mock(id="gitlab", display_name="Gitlab CI/CD")
        providers = [gitlab_provider]

        chosen_provider = _prompt_cicd_provider(providers)
        click_mock.prompt.assert_not_called()
        self.assertEqual(chosen_provider, gitlab_provider)

        jenkins_provider = Mock(id="jenkins", display_name="Jenkins")
        providers.append(jenkins_provider)
        click_mock.prompt.return_value = "2"
        chosen_provider = _prompt_cicd_provider(providers)
        click_mock.prompt.assert_called_once()
        self.assertEqual(chosen_provider, jenkins_provider)

    @patch("samcli.lib.cookiecutter.question.click")
    def test_prompt_provider_pipeline_template_will_not_prompt_if_the_list_of_templatess_has_only_one_provider(
        self, click_mock
    ):
        template1 = Mock(display_name="anyName1", location="anyLocation1", provider="a provider")
        template2 = Mock(display_name="anyName2", location="anyLocation2", provider="a provider")
        templates = [template1]

        chosen_template = _prompt_provider_pipeline_template(templates)
        click_mock.prompt.assert_not_called()
        self.assertEqual(chosen_template, template1)

        templates.append(template2)
        click_mock.prompt.return_value = "2"
        chosen_template = _prompt_provider_pipeline_template(templates)
        click_mock.prompt.assert_called_once()
        self.assertEqual(chosen_template, template2)
