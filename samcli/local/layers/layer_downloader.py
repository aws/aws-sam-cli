"""
Downloads Layers locally
"""

import errno
import logging
import uuid
from pathlib import Path
from typing import List

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from samcli.commands.local.cli_common.user_exceptions import CredentialsRequired, ResourceNotFound
from samcli.lib.providers.provider import LayerVersion, Stack
from samcli.lib.utils.codeuri import resolve_code_path
from samcli.local.common.file_lock import STATUS_COMPLETED, FileLock
from samcli.local.lambdafn.remote_files import unzip_from_uri

LOG = logging.getLogger(__name__)


class LayerDownloader:
    def __init__(self, layer_cache, cwd, stacks: List[Stack], lambda_client=None):
        """

        Parameters
        ----------
        layer_cache str
            path where to cache layers
        cwd str
            Current working directory
        stacks List[Stack]
            List of all stacks
        lambda_client boto3.client('lambda')
            Boto3 Client for AWS Lambda
        """
        self._layer_cache = layer_cache
        self.cwd = cwd
        self._stacks = stacks
        self._lambda_client = lambda_client

    @property
    def lambda_client(self):
        self._lambda_client = self._lambda_client or boto3.client("lambda")
        return self._lambda_client

    @property
    def layer_cache(self):
        """
        Layer Cache property. This will always return a cache that exists on the system.

        Returns
        -------
        str
            Path to the Layer Cache
        """
        self._create_cache(self._layer_cache)
        return self._layer_cache

    def download_all(self, layers, force=False):
        """
        Download a list of layers to the cache

        Parameters
        ----------
        layers list(samcli.commands.local.lib.provider.Layer)
            List of Layers representing the layer to be downloaded
        force bool
            True to download the layer even if it exists already on the system

        Returns
        -------
        List(Path)
            List of Paths to where the layer was cached
        """
        layer_dirs = []
        for layer in layers:
            layer_dirs.append(self.download(layer, force))

        return layer_dirs

    def download(self, layer: LayerVersion, force=False) -> LayerVersion:
        """
        Download a given layer to the local cache.

        Parameters
        ----------
        layer samcli.commands.local.lib.provider.Layer
            Layer representing the layer to be downloaded.
        force bool
            True to download the layer even if it exists already on the system

        Returns
        -------
        Path
            Path object that represents where the layer is download to
        """
        if layer.is_defined_within_template:
            LOG.info("%s is a local Layer in the template", layer.name)
            layer.codeuri = resolve_code_path(self.cwd, layer.codeuri)
            return layer

        layer_path = Path(self.layer_cache).resolve().joinpath(layer.name)
        is_layer_downloaded = self._is_layer_cached(layer_path)
        layer.codeuri = str(layer_path)

        if is_layer_downloaded and not force:
            LOG.info("%s is already cached. Skipping download", layer.arn)
            return layer

        # Use system temp directory for lock files to avoid permission issues
        lock_dir = self._get_lock_dir()
        download_lock = FileLock(lock_dir, layer.name, "downloading")

        # Try to acquire the download lock
        if download_lock.acquire_lock():
            # We got the lock, proceed with download
            try:
                # Double-check if layer was downloaded while we were waiting for the lock
                if self._is_layer_cached(layer_path) and not force:
                    LOG.info("%s was downloaded by another process. Using cached version", layer.arn)
                    download_lock.release_lock(success=True)
                    return layer

                # Create the layer directory with proper race condition handling
                self._create_layer_directory(layer_path)

                layer_zip_path = f"{layer.codeuri}_{uuid.uuid4().hex}.zip"
                layer_zip_uri = self._fetch_layer_uri(layer)
                unzip_from_uri(
                    layer_zip_uri,
                    layer_zip_path,
                    unzip_output_dir=layer.codeuri,
                    progressbar_label="Downloading {}".format(layer.layer_arn),
                )

                download_lock.release_lock(success=True)
                return layer

            except Exception as e:
                download_lock.release_lock(success=False)
                raise e
        else:
            # Another process is downloading, wait for it to complete
            LOG.info("Another process is downloading the same layer, waiting...")
            if download_lock.wait_for_operation():
                # Download completed successfully by another process
                if self._is_layer_cached(layer_path):
                    LOG.info("%s download completed by another process", layer.arn)
                    return layer
                else:
                    LOG.warning("%s download completed but layer not found, retrying", layer.arn)
                    # Retry the download
                    return self.download(layer, force=True)
            else:
                # Download failed or timed out, retry
                LOG.warning("Concurrent layer download failed or timed out, retrying")
                return self.download(layer, force=True)

    def _fetch_layer_uri(self, layer):
        """
        Fetch the Layer Uri based on the LayerVersion Arn

        Parameters
        ----------
        layer samcli.commands.local.lib.provider.LayerVersion
            LayerVersion to fetch

        Returns
        -------
        str
            The Uri to download the LayerVersion Content from

        Raises
        ------
        samcli.commands.local.cli_common.user_exceptions.NoCredentialsError
            When the Credentials given are not sufficient to call AWS Lambda
        """
        try:
            layer_version_response = self.lambda_client.get_layer_version(
                LayerName=layer.layer_arn, VersionNumber=layer.version
            )
        except NoCredentialsError as ex:
            raise CredentialsRequired("Layers require credentials to download the layers locally.") from ex
        except ClientError as e:
            error_code = e.response.get("Error").get("Code")
            error_exc = {
                "AccessDeniedException": CredentialsRequired(
                    "Credentials provided are missing lambda:Getlayerversion policy that is needed to download the "
                    "layer or you do not have permission to download the layer"
                ),
                "ResourceNotFoundException": ResourceNotFound("{} was not found.".format(layer.arn)),
            }

            if error_code in error_exc:
                raise error_exc[error_code]

            # If it was not 'AccessDeniedException' or 'ResourceNotFoundException' re-raise
            raise e

        return layer_version_response.get("Content").get("Location")

    def _is_layer_cached(self, layer_path: Path) -> bool:
        """
        Checks if the layer is already cached on the system by verifying both
        the layer directory exists and that any previous download completed successfully.

        Parameters
        ----------
        layer_path Path
            Path to where the layer should exist if cached on the system

        Returns
        -------
        bool
            True if the layer is properly cached (directory exists and download completed successfully),
            False otherwise

        """
        # First check if the layer directory exists
        if not layer_path.exists():
            return False

        # Check FileLock status to ensure the layer was downloaded successfully
        # Use the same lock directory structure as in download()
        lock_dir = self._get_lock_dir()
        layer_name = layer_path.name
        download_lock = FileLock(lock_dir, layer_name, "downloading")

        # Get the status of the last download operation
        status = download_lock._get_status()

        # Layer is considered cached if:
        # 1. Directory exists AND
        # 2. Either no status file exists (backward compatibility) OR status is completed
        if status is None:
            # No status file - assume completed for backward compatibility
            # This handles layers downloaded before FileLock status tracking
            return True
        elif status == STATUS_COMPLETED:
            # Download completed successfully
            return True
        else:
            # Download failed or is in progress - not properly cached
            LOG.debug("Layer %s exists but download status is %s, not considered cached", layer_path, status)
            return False

    @staticmethod
    def _create_cache(layer_cache):
        """
        Create the Cache directory if it does not exist.

        Parameters
        ----------
        layer_cache
            Directory to where the layers should be cached
        """
        Path(layer_cache).mkdir(mode=0o700, parents=True, exist_ok=True)

    def _get_lock_dir(self) -> Path:
        """
        Get the consistent lock directory path used for FileLock operations.
        Uses a fixed location within the layer cache directory to ensure
        consistency across processes and avoid temp directory cleanup issues.

        Returns
        -------
        Path
            Path to the lock directory
        """
        return Path(self.layer_cache) / ".locks"

    @staticmethod
    def _create_layer_directory(layer_path: Path):
        """
        Create the layer directory with proper race condition handling.

        This method handles the case where multiple processes might try to create
        the same layer directory simultaneously, which can cause FileExistsError
        even with exist_ok=True due to timing issues.

        Parameters
        ----------
        layer_path : Path
            Path to the layer directory to create
        """
        try:
            layer_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        except FileExistsError:
            # Handle race condition where another process created the directory
            # between our check and mkdir call
            if not layer_path.exists():
                # If the directory doesn't exist after FileExistsError,
                # there might be a deeper issue, so re-raise
                raise
            # Directory exists, which is what we wanted
            LOG.debug("Layer directory %s already exists (created by another process)", layer_path)
        except OSError as e:
            # Handle other OS-level errors that might occur during directory creation
            if e.errno == errno.EEXIST:  # File exists
                # Another form of the race condition
                if layer_path.exists():
                    LOG.debug("Layer directory %s already exists (race condition handled)", layer_path)
                else:
                    raise
            else:
                raise
