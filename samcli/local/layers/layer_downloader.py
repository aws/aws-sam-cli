"""
Downloads Layers locally
"""

import logging
from pathlib import Path
from typing import List

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from samcli.commands.local.cli_common.user_exceptions import CredentialsRequired, ResourceNotFound
from samcli.lib.providers.provider import LayerVersion, Stack
from samcli.lib.utils.codeuri import resolve_code_path
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

        layer_zip_path = layer.codeuri + ".zip"
        layer_zip_uri = self._fetch_layer_uri(layer)
        unzip_from_uri(
            layer_zip_uri,
            layer_zip_path,
            unzip_output_dir=layer.codeuri,
            progressbar_label="Downloading {}".format(layer.layer_arn),
        )

        return layer

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

    @staticmethod
    def _is_layer_cached(layer_path: Path) -> bool:
        """
        Checks if the layer is already cached on the system

        Parameters
        ----------
        layer_path Path
            Path to where the layer should exist if cached on the system

        Returns
        -------
        bool
            True if the layer_path already exists otherwise False

        """
        return layer_path.exists()

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
