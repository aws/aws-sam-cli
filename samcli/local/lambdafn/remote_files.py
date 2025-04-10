"""
Helper methods to handle files in remote locations.
"""

import logging
import os
from pathlib import Path

import requests

from samcli.lib.utils.progressbar import progressbar
from samcli.local.lambdafn.zip import unzip

LOG = logging.getLogger(__name__)


def unzip_from_uri(uri, layer_zip_path, unzip_output_dir, progressbar_label):
    """
    Download the LayerVersion Zip to the Layer Pkg Cache

    Parameters
    ----------
    uri str
        Uri to download from
    layer_zip_path str
        Path to where the content from the uri should be downloaded to
    unzip_output_dir str
        Path to unzip the zip to
    progressbar_label str
        Label to use in the Progressbar
    """
    try:
        get_request = requests.get(uri, stream=True, verify=os.environ.get("AWS_CA_BUNDLE") or True)

        with open(layer_zip_path, "wb") as local_layer_file:
            file_length = int(get_request.headers["Content-length"])

            with progressbar(file_length, progressbar_label) as p_bar:
                # Set the chunk size to None. Since we are streaming the request, None will allow the data to be
                # read as it arrives in whatever size the chunks are received.
                for data in get_request.iter_content(chunk_size=None):
                    local_layer_file.write(data)
                    p_bar.update(len(data))

        # Forcefully set the permissions to 700 on files and directories. This is to ensure the owner
        # of the files is the only one that can read, write, or execute the files.
        unzip(layer_zip_path, unzip_output_dir, permission=0o700)

    finally:
        # Remove the downloaded zip file
        path_to_layer = Path(layer_zip_path)
        if path_to_layer.exists():
            path_to_layer.unlink()
