import itertools
import os
from unittest import TestCase
from unittest.mock import ANY, MagicMock, Mock, patch
from parameterized import parameterized

from samcli.commands.sync.command import do_cli, execute_code_sync, execute_watch, check_enable_dependency_layer
from samcli.lib.providers.provider import ResourceIdentifier
from samcli.commands._utils.constants import (
    DEFAULT_BUILD_DIR,
    DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER,
    DEFAULT_CACHE_DIR,
)
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider
from tests.unit.commands.buildcmd.test_build_context import DummyStack


def get_mock_sam_config():
    mock_sam_config = MagicMock()
    mock_sam_config.exists = MagicMock(return_value=True)
    return mock_sam_config


MOCK_SAM_CONFIG = get_mock_sam_config()


class TestDoCli(TestCase):
    def setUp(self):

        self.template_file = "input-template-file"
        self.stack_name = "stack-name"
        self.resource_id = []
        self.resource = []
        self.image_repository = "123456789012.dkr.ecr.us-east-1.amazonaws.com/test1"
        self.image_repositories = None
        self.mode = "mode"
        self.s3_bucket = "s3-bucket"
        self.s3_prefix = "s3-prefix"
        self.kms_key_id = "kms-key-id"
        self.notification_arns = []
        self.parameter_overrides = {"a": "b"}
        self.capabilities = ("CAPABILITY_IAM",)
        self.tags = {"c": "d"}
        self.role_arn = "role_arn"
        self.metadata = {}
        self.region = None
        self.profile = None
        self.base_dir = None
        self.clean = True
        self.config_env = "mock-default-env"
        self.config_file = "mock-default-filename"
        MOCK_SAM_CONFIG.reset_mock()

    @parameterized.expand(
        [
            (False, False, True, False),
            (False, False, False, False),
            (False, False, True, True),
            (False, False, False, True),
        ]
    )
    @patch("os.environ", {**os.environ, "SAM_CLI_POLL_DELAY": 10})
    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.execute_code_sync")
    @patch("samcli.commands.build.command.click")
    @patch("samcli.commands.build.build_context.BuildContext")
    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.build.command.os")
    @patch("samcli.commands.sync.command.manage_stack")
    @patch("samcli.commands.sync.command.SyncContext")
    @patch("samcli.commands.sync.command.check_enable_dependency_layer")
    def test_infra_must_succeed_sync(
        self,
        code,
        watch,
        auto_dependency_layer,
        use_container,
        check_enable_adl_mock,
        SyncContextMock,
        manage_stack_mock,
        os_mock,
        DeployContextMock,
        mock_deploy_click,
        PackageContextMock,
        mock_package_click,
        BuildContextMock,
        mock_build_click,
        execute_code_sync_mock,
        click_mock,
    ):

        build_context_mock = Mock()
        BuildContextMock.return_value.__enter__.return_value = build_context_mock
        package_context_mock = Mock()
        PackageContextMock.return_value.__enter__.return_value = package_context_mock
        deploy_context_mock = Mock()
        DeployContextMock.return_value.__enter__.return_value = deploy_context_mock
        sync_context_mock = Mock()
        SyncContextMock.return_value.__enter__.return_value = sync_context_mock

        check_enable_adl_mock.return_value = auto_dependency_layer

        do_cli(
            self.template_file,
            False,
            False,
            self.resource_id,
            self.resource,
            auto_dependency_layer,
            self.stack_name,
            self.region,
            self.profile,
            self.base_dir,
            self.parameter_overrides,
            self.mode,
            self.image_repository,
            self.image_repositories,
            self.s3_bucket,
            self.s3_prefix,
            self.kms_key_id,
            self.capabilities,
            self.role_arn,
            self.notification_arns,
            self.tags,
            self.metadata,
            use_container,
            self.config_file,
            self.config_env,
            build_in_source=False,
        )

        if use_container and auto_dependency_layer:
            auto_dependency_layer = False

        build_dir = DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER if auto_dependency_layer else DEFAULT_BUILD_DIR
        BuildContextMock.assert_called_with(
            resource_identifier=None,
            template_file=self.template_file,
            base_dir=self.base_dir,
            build_dir=build_dir,
            cache_dir=DEFAULT_CACHE_DIR,
            clean=True,
            use_container=use_container,
            parallel=True,
            parameter_overrides=self.parameter_overrides,
            mode=self.mode,
            cached=True,
            create_auto_dependency_layer=auto_dependency_layer,
            stack_name=self.stack_name,
            print_success_message=False,
            locate_layer_nested=True,
            build_in_source=False,
        )

        PackageContextMock.assert_called_with(
            template_file=ANY,
            s3_bucket=ANY,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            output_template_file=ANY,
            no_progressbar=True,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
            use_json=False,
            force_upload=True,
        )

        DeployContextMock.assert_called_with(
            template_file=ANY,
            stack_name=self.stack_name,
            s3_bucket=ANY,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            no_progressbar=True,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            tags=self.tags,
            region=self.region,
            profile=self.profile,
            no_execute_changeset=True,
            fail_on_empty_changeset=True,
            confirm_changeset=False,
            use_changeset=False,
            force_upload=True,
            signing_profiles=None,
            disable_rollback=False,
            poll_delay=10,
            on_failure=None,
        )
        build_context_mock.run.assert_called_once_with()
        package_context_mock.run.assert_called_once_with()
        deploy_context_mock.run.assert_called_once_with()
        execute_code_sync_mock.assert_not_called()

    @parameterized.expand([(False, True, False, False), (False, True, False, True)])
    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.execute_watch")
    @patch("samcli.commands.build.command.click")
    @patch("samcli.commands.build.build_context.BuildContext")
    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.build.command.os")
    @patch("samcli.commands.sync.command.manage_stack")
    @patch("samcli.commands.sync.command.SyncContext")
    def test_watch_must_succeed_sync(
        self,
        code,
        watch,
        auto_dependency_layer,
        use_container,
        SyncContextMock,
        manage_stack_mock,
        os_mock,
        DeployContextMock,
        mock_deploy_click,
        PackageContextMock,
        mock_package_click,
        BuildContextMock,
        mock_build_click,
        execute_watch_mock,
        click_mock,
    ):
        skip_infra_syncs = watch and code
        build_context_mock = Mock()
        BuildContextMock.return_value.__enter__.return_value = build_context_mock
        package_context_mock = Mock()
        PackageContextMock.return_value.__enter__.return_value = package_context_mock
        deploy_context_mock = Mock()
        DeployContextMock.return_value.__enter__.return_value = deploy_context_mock
        sync_context_mock = Mock()
        SyncContextMock.return_value.__enter__.return_value = sync_context_mock

        do_cli(
            self.template_file,
            False,
            True,
            self.resource_id,
            self.resource,
            auto_dependency_layer,
            self.stack_name,
            self.region,
            self.profile,
            self.base_dir,
            self.parameter_overrides,
            self.mode,
            self.image_repository,
            self.image_repositories,
            self.s3_bucket,
            self.s3_prefix,
            self.kms_key_id,
            self.capabilities,
            self.role_arn,
            self.notification_arns,
            self.tags,
            self.metadata,
            use_container,
            self.config_file,
            self.config_env,
            build_in_source=False,
        )

        BuildContextMock.assert_called_with(
            resource_identifier=None,
            template_file=self.template_file,
            base_dir=self.base_dir,
            build_dir=DEFAULT_BUILD_DIR,
            cache_dir=DEFAULT_CACHE_DIR,
            clean=True,
            use_container=use_container,
            parallel=True,
            parameter_overrides=self.parameter_overrides,
            mode=self.mode,
            cached=True,
            create_auto_dependency_layer=auto_dependency_layer,
            stack_name=self.stack_name,
            print_success_message=False,
            locate_layer_nested=True,
            build_in_source=False,
        )

        PackageContextMock.assert_called_with(
            template_file=ANY,
            s3_bucket=ANY,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            output_template_file=ANY,
            no_progressbar=True,
            metadata=self.metadata,
            region=self.region,
            profile=self.profile,
            use_json=False,
            force_upload=True,
        )

        DeployContextMock.assert_called_with(
            template_file=ANY,
            stack_name=self.stack_name,
            s3_bucket=ANY,
            image_repository=self.image_repository,
            image_repositories=self.image_repositories,
            no_progressbar=True,
            s3_prefix=self.s3_prefix,
            kms_key_id=self.kms_key_id,
            parameter_overrides=self.parameter_overrides,
            capabilities=self.capabilities,
            role_arn=self.role_arn,
            notification_arns=self.notification_arns,
            tags=self.tags,
            region=self.region,
            profile=self.profile,
            no_execute_changeset=True,
            fail_on_empty_changeset=True,
            confirm_changeset=False,
            use_changeset=False,
            force_upload=True,
            signing_profiles=None,
            disable_rollback=False,
            poll_delay=0.5,
            on_failure=None,
        )
        execute_watch_mock.assert_called_once_with(
            self.template_file,
            build_context_mock,
            package_context_mock,
            deploy_context_mock,
            sync_context_mock,
            auto_dependency_layer,
            skip_infra_syncs,
        )

    @parameterized.expand([(True, False, True, False), (True, False, False, True)])
    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.execute_code_sync")
    @patch("samcli.commands.build.command.click")
    @patch("samcli.commands.build.build_context.BuildContext")
    @patch("samcli.commands.package.command.click")
    @patch("samcli.commands.package.package_context.PackageContext")
    @patch("samcli.commands.deploy.command.click")
    @patch("samcli.commands.deploy.deploy_context.DeployContext")
    @patch("samcli.commands.build.command.os")
    @patch("samcli.commands.sync.command.manage_stack")
    @patch("samcli.commands.sync.command.SyncContext")
    @patch("samcli.commands.sync.command.check_enable_dependency_layer")
    def test_code_must_succeed_sync(
        self,
        code,
        watch,
        auto_dependency_layer,
        use_container,
        check_enable_adl_mock,
        SyncContextMock,
        manage_stack_mock,
        os_mock,
        DeployContextMock,
        mock_deploy_click,
        PackageContextMock,
        mock_package_click,
        BuildContextMock,
        mock_build_click,
        execute_code_sync_mock,
        click_mock,
    ):

        build_context_mock = Mock()
        BuildContextMock.return_value.__enter__.return_value = build_context_mock
        package_context_mock = Mock()
        PackageContextMock.return_value.__enter__.return_value = package_context_mock
        deploy_context_mock = Mock()
        DeployContextMock.return_value.__enter__.return_value = deploy_context_mock
        sync_context_mock = Mock()
        SyncContextMock.return_value.__enter__.return_value = sync_context_mock

        check_enable_adl_mock.return_value = auto_dependency_layer

        do_cli(
            self.template_file,
            True,
            False,
            self.resource_id,
            self.resource,
            auto_dependency_layer,
            self.stack_name,
            self.region,
            self.profile,
            self.base_dir,
            self.parameter_overrides,
            self.mode,
            self.image_repository,
            self.image_repositories,
            self.s3_bucket,
            self.s3_prefix,
            self.kms_key_id,
            self.capabilities,
            self.role_arn,
            self.notification_arns,
            self.tags,
            self.metadata,
            use_container,
            self.config_file,
            self.config_env,
            build_in_source=None,
        )
        execute_code_sync_mock.assert_called_once_with(
            self.template_file,
            build_context_mock,
            deploy_context_mock,
            sync_context_mock,
            self.resource_id,
            self.resource,
            auto_dependency_layer,
        )


class TestSyncCode(TestCase):
    def setUp(self) -> None:
        self.template_file = "template.yaml"
        self.build_context = MagicMock()
        self.deploy_context = MagicMock()
        self.sync_context = MagicMock()

    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.sync.command.SyncFlowFactory")
    @patch("samcli.commands.sync.command.SyncFlowExecutor")
    @patch("samcli.commands.sync.command.get_unique_resource_ids")
    def test_execute_code_sync_single_resource(
        self,
        get_unique_resource_ids_mock,
        sync_flow_executor_mock,
        sync_flow_factory_mock,
        get_stacks_mock,
        click_mock,
    ):

        resource_identifier_strings = ["Function1"]
        resource_types = []
        sync_flows = [MagicMock()]
        sync_flow_factory_mock.return_value.create_sync_flow.side_effect = sync_flows
        get_unique_resource_ids_mock.return_value = {
            ResourceIdentifier("Function1"),
        }

        execute_code_sync(
            self.template_file,
            self.build_context,
            self.deploy_context,
            self.sync_context,
            resource_identifier_strings,
            resource_types,
            True,
        )

        sync_flow_factory_mock.return_value.create_sync_flow.assert_called_once_with(ResourceIdentifier("Function1"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_called_once_with(sync_flows[0])

        get_unique_resource_ids_mock.assert_called_once_with(
            get_stacks_mock.return_value[0], resource_identifier_strings, []
        )

    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.sync.command.SyncFlowFactory")
    @patch("samcli.commands.sync.command.SyncFlowExecutor")
    @patch("samcli.commands.sync.command.get_unique_resource_ids")
    def test_execute_code_sync_multiple_resource(
        self,
        get_unique_resource_ids_mock,
        sync_flow_executor_mock,
        sync_flow_factory_mock,
        get_stacks_mock,
        click_mock,
    ):

        resource_identifier_strings = ["Function1", "Function2"]
        resource_types = []
        sync_flows = [MagicMock(), MagicMock()]
        sync_flow_factory_mock.return_value.create_sync_flow.side_effect = sync_flows
        get_unique_resource_ids_mock.return_value = {
            ResourceIdentifier("Function1"),
            ResourceIdentifier("Function2"),
        }

        execute_code_sync(
            self.template_file,
            self.build_context,
            self.deploy_context,
            self.sync_context,
            resource_identifier_strings,
            resource_types,
            True,
        )

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function1"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[0])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function2"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[1])

        self.assertEqual(sync_flow_factory_mock.return_value.create_sync_flow.call_count, 2)
        self.assertEqual(sync_flow_executor_mock.return_value.add_sync_flow.call_count, 2)

        get_unique_resource_ids_mock.assert_called_once_with(
            get_stacks_mock.return_value[0], resource_identifier_strings, []
        )

    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.sync.command.SyncFlowFactory")
    @patch("samcli.commands.sync.command.SyncFlowExecutor")
    @patch("samcli.commands.sync.command.get_unique_resource_ids")
    def test_execute_code_sync_single_type_resource(
        self,
        get_unique_resource_ids_mock,
        sync_flow_executor_mock,
        sync_flow_factory_mock,
        get_stacks_mock,
        click_mock,
    ):

        resource_identifier_strings = ["Function1", "Function2"]
        resource_types = ["AWS::Serverless::Function"]
        sync_flows = [MagicMock(), MagicMock(), MagicMock()]
        sync_flow_factory_mock.return_value.create_sync_flow.side_effect = sync_flows
        get_unique_resource_ids_mock.return_value = {
            ResourceIdentifier("Function1"),
            ResourceIdentifier("Function2"),
            ResourceIdentifier("Function3"),
        }

        execute_code_sync(
            self.template_file,
            self.build_context,
            self.deploy_context,
            self.sync_context,
            resource_identifier_strings,
            resource_types,
            True,
        )

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function1"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[0])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function2"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[1])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function3"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[2])

        self.assertEqual(sync_flow_factory_mock.return_value.create_sync_flow.call_count, 3)
        self.assertEqual(sync_flow_executor_mock.return_value.add_sync_flow.call_count, 3)

        get_unique_resource_ids_mock.assert_called_once_with(
            get_stacks_mock.return_value[0], resource_identifier_strings, ["AWS::Serverless::Function"]
        )

    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.sync.command.SyncFlowFactory")
    @patch("samcli.commands.sync.command.SyncFlowExecutor")
    @patch("samcli.commands.sync.command.get_unique_resource_ids")
    def test_execute_code_sync_multiple_type_resource(
        self,
        get_unique_resource_ids_mock,
        sync_flow_executor_mock,
        sync_flow_factory_mock,
        get_stacks_mock,
        click_mock,
    ):
        resource_identifier_strings = ["Function1", "Function2"]
        resource_types = ["AWS::Serverless::Function", "AWS::Serverless::LayerVersion"]
        sync_flows = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        sync_flow_factory_mock.return_value.create_sync_flow.side_effect = sync_flows
        get_unique_resource_ids_mock.return_value = {
            ResourceIdentifier("Function1"),
            ResourceIdentifier("Function2"),
            ResourceIdentifier("Function3"),
            ResourceIdentifier("Function4"),
        }

        execute_code_sync(
            self.template_file,
            self.build_context,
            self.deploy_context,
            self.sync_context,
            resource_identifier_strings,
            resource_types,
            True,
        )

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function1"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[0])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function2"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[1])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function3"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[2])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function4"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[3])

        self.assertEqual(sync_flow_factory_mock.return_value.create_sync_flow.call_count, 4)
        self.assertEqual(sync_flow_executor_mock.return_value.add_sync_flow.call_count, 4)

        get_unique_resource_ids_mock.assert_any_call(
            get_stacks_mock.return_value[0],
            resource_identifier_strings,
            ["AWS::Serverless::Function", "AWS::Serverless::LayerVersion"],
        )

    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.SamLocalStackProvider.get_stacks")
    @patch("samcli.commands.sync.command.SyncFlowFactory")
    @patch("samcli.commands.sync.command.SyncFlowExecutor")
    @patch("samcli.commands.sync.command.get_all_resource_ids")
    def test_execute_code_sync_default_all_resources(
        self,
        get_all_resource_ids_mock,
        sync_flow_executor_mock,
        sync_flow_factory_mock,
        get_stacks_mock,
        click_mock,
    ):
        sync_flows = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
        sync_flow_factory_mock.return_value.create_sync_flow.side_effect = sync_flows
        get_all_resource_ids_mock.return_value = [
            ResourceIdentifier("Function1"),
            ResourceIdentifier("Function2"),
            ResourceIdentifier("Function3"),
            ResourceIdentifier("Function4"),
        ]

        execute_code_sync(self.template_file, self.build_context, self.deploy_context, self.sync_context, "", [], True)

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function1"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[0])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function2"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[1])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function3"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[2])

        sync_flow_factory_mock.return_value.create_sync_flow.assert_any_call(ResourceIdentifier("Function4"))
        sync_flow_executor_mock.return_value.add_sync_flow.assert_any_call(sync_flows[3])

        self.assertEqual(sync_flow_factory_mock.return_value.create_sync_flow.call_count, 4)
        self.assertEqual(sync_flow_executor_mock.return_value.add_sync_flow.call_count, 4)

        get_all_resource_ids_mock.assert_called_once_with(get_stacks_mock.return_value[0])


class TestWatch(TestCase):
    def setUp(self) -> None:
        self.template_file = "template.yaml"
        self.build_context = MagicMock()
        self.package_context = MagicMock()
        self.deploy_context = MagicMock()
        self.sync_context = MagicMock()

    @parameterized.expand(itertools.product([True, False], [True, False]))
    @patch("samcli.commands.sync.command.click")
    @patch("samcli.commands.sync.command.WatchManager")
    def test_execute_watch(
        self,
        code,
        auto_dependency_layer,
        watch_manager_mock,
        click_mock,
    ):
        skip_infra_syncs = code
        execute_watch(
            self.template_file,
            self.build_context,
            self.package_context,
            self.deploy_context,
            self.sync_context,
            auto_dependency_layer,
            skip_infra_syncs,
        )

        watch_manager_mock.assert_called_once_with(
            self.template_file,
            self.build_context,
            self.package_context,
            self.deploy_context,
            self.sync_context,
            auto_dependency_layer,
            skip_infra_syncs,
        )
        watch_manager_mock.return_value.start.assert_called_once_with()


class TestDisableADL(TestCase):
    @parameterized.expand(
        [
            (
                {
                    "test": {
                        "Properties": {
                            "Environment": {"Variables": {"NODE_OPTIONS": ["--something"]}},
                        },
                        "Metadata": {"BuildMethod": "esbuild", "BuildProperties": {"Sourcemap": True}},
                        "Type": "AWS::Serverless::Function",
                    }
                },
                False,
            ),
            (
                {
                    "test": {
                        "Properties": {
                            "Environment": {"Variables": {"NODE_OPTIONS": ["--something"]}},
                        },
                        "Type": "AWS::Serverless::Function",
                    }
                },
                True,
            ),
        ]
    )
    @patch("samcli.commands.sync.command.SamLocalStackProvider")
    def test_disables_adl_for_esbuild(self, stack_resources, expected, provider_mock):
        stack = DummyStack(stack_resources)
        stack.stack_path = "/path"
        stack.location = "/location"
        provider_mock.get_stacks.return_value = (
            [stack],
            "",
        )
        self.assertEqual(check_enable_dependency_layer("/template/file"), expected)
