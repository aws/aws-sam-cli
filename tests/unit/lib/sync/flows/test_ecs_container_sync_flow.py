from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from botocore.exceptions import ClientError

from samcli.lib.sync.flows.ecs_container_sync_flow import ECSContainerSyncFlow
from samcli.lib.sync.sync_flow import ApiCallTypes


def _make_client_error(code="SomeError"):
    err = ClientError({"Error": {"Code": code, "Message": "msg"}}, "op")
    return err


def _make_flow(image_repository="123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo", stacks=None):
    build_context = MagicMock()
    deploy_context = MagicMock()
    deploy_context.image_repository = image_repository
    deploy_context.image_repositories = None
    flow = ECSContainerSyncFlow(
        "MyTask",
        build_context=build_context,
        deploy_context=deploy_context,
        sync_context=MagicMock(),
        physical_id_mapping={"MyTask": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5"},
        stacks=stacks or [],
        application_build_result=None,
    )
    flow._image_name = "myapp:latest"
    return flow


class TestECSContainerSyncFlowApiCallTypes(TestCase):
    def test_get_resource_api_calls_uses_update_container_image(self):
        flow = _make_flow()
        calls = flow._get_resource_api_calls()
        self.assertEqual(1, len(calls))
        self.assertIn(ApiCallTypes.UPDATE_CONTAINER_IMAGE, calls[0].api_calls)

    def test_equality_keys(self):
        flow = _make_flow()
        self.assertEqual("MyTask", flow._equality_keys())

    def test_sync_state_identifier(self):
        flow = _make_flow()
        self.assertEqual("MyTask", flow.sync_state_identifier)


class TestECSContainerSyncFlowSync(TestCase):
    def _make_ecs_client(self, container_name="app", image_uri="old-image:1"):
        ecs_client = MagicMock()
        task_def = {
            "taskDefinitionArn": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5",
            "family": "mytask",
            "revision": 5,
            "status": "ACTIVE",
            "containerDefinitions": [{"name": container_name, "image": image_uri}],
            "requiresAttributes": [],
            "compatibilities": ["EC2"],
        }
        ecs_client.describe_task_definition.return_value = {"taskDefinition": task_def, "tags": []}
        ecs_client.register_task_definition.return_value = {
            "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:us-east-1:123:task-definition/mytask:6"}
        }
        ecs_client.describe_services.return_value = {
            "services": [{"taskDefinition": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5"}]
        }
        return ecs_client

    def test_sync_registers_new_task_definition_and_updates_service(self):
        flow = _make_flow()
        # Include a service ARN so _update_services_to_task_definition can match it
        flow._physical_id_mapping = {
            "MyTask": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5",
            "MyService": "arn:aws:ecs:us-east-1:123:service/mycluster/mysvc",
        }
        ecr_client = MagicMock()
        docker_client = MagicMock()
        ecs_client = self._make_ecs_client()

        flow._ecr_client = ecr_client
        flow._docker_client = docker_client
        flow._ecs_client = ecs_client

        with patch(
            "samcli.lib.sync.flows.ecs_container_sync_flow.ECRUploader"
        ) as MockUploader, patch.object(flow, "_get_container_name", return_value=None):
            mock_uploader_instance = MagicMock()
            mock_uploader_instance.upload.return_value = (
                "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo:newtag"
            )
            MockUploader.return_value = mock_uploader_instance

            flow.sync()

        ecs_client.describe_task_definition.assert_called_once_with(
            taskDefinition="arn:aws:ecs:us-east-1:123:task-definition/mytask:5", include=["TAGS"]
        )
        # register_task_definition should be called with updated image
        reg_call_kwargs = ecs_client.register_task_definition.call_args[1]
        self.assertEqual(
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/myrepo:newtag",
            reg_call_kwargs["containerDefinitions"][0]["image"],
        )
        # update_service should target the new revision
        ecs_client.update_service.assert_called_once()
        update_kwargs = ecs_client.update_service.call_args[1]
        self.assertEqual("arn:aws:ecs:us-east-1:123:task-definition/mytask:6", update_kwargs["taskDefinition"])

    def test_sync_skips_when_no_image_name(self):
        flow = _make_flow()
        flow._image_name = None
        ecs_client = MagicMock()
        flow._ecs_client = ecs_client

        flow.sync()

        ecs_client.describe_task_definition.assert_not_called()

    def test_sync_skips_when_no_ecr_repo(self):
        flow = _make_flow(image_repository=None)
        flow._image_name = "myapp:latest"
        ecs_client = MagicMock()
        flow._ecs_client = ecs_client

        flow.sync()

        ecs_client.describe_task_definition.assert_not_called()

    def test_register_returns_none_when_describe_fails(self):
        flow = _make_flow()
        ecs_client = MagicMock()
        ecs_client.describe_task_definition.side_effect = _make_client_error("AccessDenied")
        flow._ecs_client = ecs_client

        result = flow._register_updated_task_definition("new-image:uri")
        self.assertIsNone(result)

    def test_register_returns_none_when_no_physical_id(self):
        flow = _make_flow()
        flow._physical_id_mapping = {}
        result = flow._register_updated_task_definition("new-image:uri")
        self.assertIsNone(result)

    def test_update_services_skips_non_ecs_arns(self):
        flow = _make_flow()
        flow._physical_id_mapping = {
            "MyTask": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5",
            # App Runner ARN — must NOT trigger describe_services
            "AppRunnerSvc": "arn:aws:apprunner:us-east-1:123:service/mysvc/abc123",
        }
        ecs_client = MagicMock()
        flow._ecs_client = ecs_client

        flow._update_services_to_task_definition("arn:aws:ecs:us-east-1:123:task-definition/mytask:6")

        ecs_client.describe_services.assert_not_called()

    def test_update_services_updates_matching_service(self):
        flow = _make_flow()
        flow._physical_id_mapping = {
            "MyTask": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5",
            "MyService": "arn:aws:ecs:us-east-1:123:service/mycluster/mysvc",
        }
        ecs_client = MagicMock()
        ecs_client.describe_services.return_value = {
            "services": [{"taskDefinition": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5"}]
        }
        flow._ecs_client = ecs_client

        new_arn = "arn:aws:ecs:us-east-1:123:task-definition/mytask:6"
        flow._update_services_to_task_definition(new_arn)

        ecs_client.update_service.assert_called_once_with(
            cluster="mycluster", service="mysvc", taskDefinition=new_arn
        )

    def test_update_services_skips_mismatched_family(self):
        flow = _make_flow()
        flow._physical_id_mapping = {
            "MyTask": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5",
            "OtherService": "arn:aws:ecs:us-east-1:123:service/mycluster/othersvc",
        }
        ecs_client = MagicMock()
        ecs_client.describe_services.return_value = {
            "services": [{"taskDefinition": "arn:aws:ecs:us-east-1:123:task-definition/othertask:3"}]
        }
        flow._ecs_client = ecs_client

        flow._update_services_to_task_definition("arn:aws:ecs:us-east-1:123:task-definition/mytask:6")

        ecs_client.update_service.assert_not_called()

    def test_update_services_handles_describe_client_error(self):
        flow = _make_flow()
        flow._physical_id_mapping = {
            "MyTask": "arn:aws:ecs:us-east-1:123:task-definition/mytask:5",
            "MyService": "arn:aws:ecs:us-east-1:123:service/mycluster/mysvc",
        }
        ecs_client = MagicMock()
        ecs_client.describe_services.side_effect = _make_client_error("AccessDenied")
        flow._ecs_client = ecs_client

        # Should not raise
        flow._update_services_to_task_definition("arn:aws:ecs:us-east-1:123:task-definition/mytask:6")
        ecs_client.update_service.assert_not_called()

    def test_register_strips_readonly_fields(self):
        flow = _make_flow()
        ecs_client = self._make_ecs_client()
        flow._ecs_client = ecs_client

        with patch.object(flow, "_get_container_name", return_value=None):
            flow._register_updated_task_definition("new-image:uri")

        reg_kwargs = ecs_client.register_task_definition.call_args[1]
        for field in ("taskDefinitionArn", "revision", "status", "requiresAttributes", "compatibilities"):
            self.assertNotIn(field, reg_kwargs, f"readonly field '{field}' should be stripped")

    def test_register_tags_included_when_present(self):
        flow = _make_flow()
        ecs_client = self._make_ecs_client()
        ecs_client.describe_task_definition.return_value = {
            "taskDefinition": {
                "family": "mytask",
                "containerDefinitions": [{"name": "app", "image": "old"}],
            },
            "tags": [{"key": "env", "value": "prod"}],
        }
        flow._ecs_client = ecs_client

        with patch.object(flow, "_get_container_name", return_value=None):
            flow._register_updated_task_definition("new-image:uri")

        reg_kwargs = ecs_client.register_task_definition.call_args[1]
        self.assertEqual([{"key": "env", "value": "prod"}], reg_kwargs.get("tags"))

    def test_register_updates_named_container(self):
        flow = _make_flow()
        ecs_client = MagicMock()
        ecs_client.describe_task_definition.return_value = {
            "taskDefinition": {
                "family": "mytask",
                "containerDefinitions": [
                    {"name": "sidecar", "image": "sidecar:old"},
                    {"name": "app", "image": "app:old"},
                ],
            },
            "tags": [],
        }
        ecs_client.register_task_definition.return_value = {
            "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:us-east-1:123:task-definition/mytask:6"}
        }
        flow._ecs_client = ecs_client

        with patch.object(flow, "_get_container_name", return_value="app"):
            flow._register_updated_task_definition("new-image:uri")

        reg_kwargs = ecs_client.register_task_definition.call_args[1]
        containers = {cd["name"]: cd["image"] for cd in reg_kwargs["containerDefinitions"]}
        self.assertEqual("new-image:uri", containers["app"])
        self.assertEqual("sidecar:old", containers["sidecar"])

    def test_register_returns_none_when_named_container_missing(self):
        flow = _make_flow()
        ecs_client = MagicMock()
        ecs_client.describe_task_definition.return_value = {
            "taskDefinition": {
                "family": "mytask",
                "containerDefinitions": [{"name": "other", "image": "img"}],
            },
            "tags": [],
        }
        flow._ecs_client = ecs_client

        with patch.object(flow, "_get_container_name", return_value="app"):
            result = flow._register_updated_task_definition("new-image:uri")

        self.assertIsNone(result)
        ecs_client.register_task_definition.assert_not_called()


class TestECSContainerSyncFlowGatherResources(TestCase):
    def test_gather_resources_uses_prebuilt_artifacts(self):
        build_result = MagicMock()
        build_result.artifacts = {"MyTask": "prebuilt-image:tag"}

        docker_client = MagicMock()
        img = MagicMock()
        img.attrs = {"Id": "sha256:abc"}
        docker_client.images.get.return_value = img

        flow = ECSContainerSyncFlow(
            "MyTask",
            build_context=MagicMock(),
            deploy_context=MagicMock(),
            sync_context=MagicMock(),
            physical_id_mapping={},
            stacks=[],
            application_build_result=build_result,
        )
        flow._docker_client = docker_client
        flow.gather_resources()

        self.assertEqual("prebuilt-image:tag", flow._image_name)
        self.assertEqual("sha256:abc", flow._local_sha)
