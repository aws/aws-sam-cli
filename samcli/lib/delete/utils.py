"""
Utilities for Delete
"""

from samcli.lib.utils.hash import file_checksum
from samcli.lib.package.artifact_exporter import mktempfile

def get_cf_template_name(template_str, extension):
    with mktempfile() as temp_file:
        temp_file.write(template_str)
        temp_file.flush()

        filemd5 = file_checksum(temp_file.name)
        remote_path = filemd5 + "." + extension

        return remote_path
