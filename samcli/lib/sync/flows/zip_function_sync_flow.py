"""SyncFlow for ZIP based Lambda Functions"""
import hashlib
import logging
import os
import base64
import tempfile
import uuid

from contextlib import ExitStack
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

from samcli.lib.build.build_graph import BuildGraph
from samcli.lib.providers.provider import Stack

from samcli.lib.sync.flows.function_sync_flow import FunctionSyncFlow
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.utils.hash import file_checksum
from samcli.lib.package.utils import make_zip

from samcli.lib.build.app_builder import ApplicationBuilder
from samcli.lib.sync.sync_flow import ResourceAPICall

if TYPE_CHECKING:  # pragma: no cover
    from samcli.commands.deploy.deploy_context import DeployContext
    from samcli.commands.build.build_context import BuildContext

LOG = logging.getLogger(__name__)
MAXIMUM_FUNCTION_ZIP_SIZE = 50 * 1024 * 1024  # 50MB limit for Lambda direct ZIP upload


class ZipFunctionSyncFlow(FunctionSyncFlow):
    """SyncFlow for ZIP based functions"""

    _s3_client: Any
    _artifact_folder: Optional[str]
    _zip_file: Optional[str]
    _local_sha: Optional[str]
    _build_graph: Optional[BuildGraph]

    def __init__(
        self,
        function_identifier: str,
        build_context: "BuildContext",
        deploy_context: "DeployContext",
        physical_id_mapping: Dict[str, str],
        stacks: List[Stack],
    ):

        """
        Parameters
        ----------
        function_identifier : str
            ZIP function resource identifier that need to be synced.
        build_context : BuildContext
            BuildContext
        deploy_context : DeployContext
            DeployContext
        physical_id_mapping : Dict[str, str]
            Physical ID Mapping
        stacks : Optional[List[Stack]]
            Stacks
        """
        super().__init__(function_identifier, build_context, deploy_context, physical_id_mapping, stacks)
        self._s3_client = None
        self._artifact_folder = None
        self._zip_file = None
        self._local_sha = None
        self._build_graph = None

    def set_up(self) -> None:
        super().set_up()
        self._s3_client = self._boto_client("s3")

    def gather_resources(self) -> None:
        """Build function and ZIP it into a temp file in self._zip_file"""
        with ExitStack() as exit_stack:
            if self._function.layers:
                exit_stack.enter_context(self._get_lock_chain())

            builder = ApplicationBuilder(
                self._build_context.collect_build_resources(self._function_identifier),
                self._build_context.build_dir,
                self._build_context.base_dir,
                self._build_context.cache_dir,
                cached=True,
                is_building_specific_resource=True,
                manifest_path_override=self._build_context.manifest_path_override,
                container_manager=self._build_context.container_manager,
                mode=self._build_context.mode,
                combine_dependencies=self._combine_dependencies(),
            )
            LOG.debug("%sBuilding Function", self.log_prefix)
            build_result = builder.build()
            self._build_graph = build_result.build_graph
            self._artifact_folder = build_result.artifacts.get(self._function_identifier)

        zip_file_path = os.path.join(tempfile.gettempdir(), "data-" + uuid.uuid4().hex)
        self._zip_file = make_zip(zip_file_path, self._artifact_folder)
        LOG.debug("%sCreated artifact ZIP file: %s", self.log_prefix, self._zip_file)
        self._local_sha = file_checksum(cast(str, self._zip_file), hashlib.sha256())

    def compare_remote(self) -> bool:
        remote_info = self._lambda_client.get_function(FunctionName=self.get_physical_id(self._function_identifier))
        remote_sha = base64.b64decode(remote_info["Configuration"]["CodeSha256"]).hex()
        LOG.debug("%sLocal SHA: %s Remote SHA: %s", self.log_prefix, self._local_sha, remote_sha)

        return self._local_sha == remote_sha

    def sync(self) -> None:
        if not self._zip_file:
            LOG.debug("%sSkipping Sync. ZIP file is None.", self.log_prefix)
            return

        zip_file_size = os.path.getsize(self._zip_file)
        if zip_file_size < MAXIMUM_FUNCTION_ZIP_SIZE:
            # Direct upload through Lambda API
            LOG.debug("%sUploading Function Directly", self.log_prefix)
            with open(self._zip_file, "rb") as zip_file:
                data = zip_file.read()
                self._lambda_client.update_function_code(
                    FunctionName=self.get_physical_id(self._function_identifier), ZipFile=data
                )
        else:
            # Upload to S3 first for oversized ZIPs
            LOG.debug("%sUploading Function Through S3", self.log_prefix)
            uploader = S3Uploader(
                s3_client=self._s3_client,
                bucket_name=self._deploy_context.s3_bucket,
                prefix=self._deploy_context.s3_prefix,
                kms_key_id=self._deploy_context.kms_key_id,
                force_upload=True,
                no_progressbar=True,
            )
            s3_url = uploader.upload_with_dedup(self._zip_file)
            s3_key = s3_url[5:].split("/", 1)[1]
            self._lambda_client.update_function_code(
                FunctionName=self.get_physical_id(self._function_identifier),
                S3Bucket=self._deploy_context.s3_bucket,
                S3Key=s3_key,
            )

        if os.path.exists(self._zip_file):
            os.remove(self._zip_file)

    def _get_resource_api_calls(self) -> List[ResourceAPICall]:
        resource_calls = list()
        for layer in self._function.layers:
            resource_calls.append(ResourceAPICall(layer.full_path, ["Build"]))
        return resource_calls

    @staticmethod
    def _combine_dependencies() -> bool:
        return True
