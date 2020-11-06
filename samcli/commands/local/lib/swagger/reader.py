"""
Read Swagger documents from variety of sources
"""

import os
import tempfile
import logging

from urllib.parse import urlparse, parse_qs

import boto3
import botocore

from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)
_FN_TRANSFORM = "Fn::Transform"


def parse_aws_include_transform(data):
    """
    If the input data is an AWS::Include data, then parse and return the location of the included file.

    AWS::Include transform data usually has the following format:
    {
        "Fn::Transform": {
            "Name": "AWS::Include",
            "Parameters": {
                "Location": "s3://MyAmazonS3BucketName/swagger.yaml"
            }
        }
    }

    Parameters
    ----------
    data : dict
        Dictionary data to parse

    Returns
    -------
    str
        Location of the included file, if available. None, otherwise
    """

    if not data:
        return None

    if _FN_TRANSFORM not in data:
        return None

    transform_data = data[_FN_TRANSFORM]

    name = transform_data.get("Name")
    location = transform_data.get("Parameters", {}).get("Location")
    if name == "AWS::Include":
        LOG.debug("Successfully parsed location from AWS::Include transform: %s", location)
        return location

    return None


class SwaggerReader:
    """
    Class to read and parse Swagger document from a variety of sources. This class accepts the same data formats as
    available in Serverless::Api SAM resource
    """

    def __init__(self, definition_body=None, definition_uri=None, working_dir=None):
        """
        Initialize the class with swagger location

        Parameters
        ----------
        definition_body : dict
            Swagger document as a dictionary directly or inlined using AWS::Include transform.

        definition_uri : str or dict
            Location of the Swagger file. Supports three formats:
                - S3 URI Ex: ``s3://mybucket/swagger.yaml``
                - S3 URI as a dictionary Ex: ``{"Bucket": "mybucket", "Key": "swagger.yaml", "Version": "123"}``
                - Local file path either as absolute or relative path Ex: ``./swagger.yaml``. Relative paths are
                  resolved to with respect to the given working directory.

        working_dir : str
            Path to the working directory with respect which we will resolve local relative paths
        """
        self.definition_body = definition_body
        self.definition_uri = definition_uri
        self.working_dir = working_dir

        if not self.definition_body and not self.definition_uri:
            raise ValueError("Require value for either DefinitionBody or DefinitionUri")

    def read(self):
        """
        Gets the Swagger document from either of the given locations. If we fail to retrieve or parse the Swagger
        file, this method will return None.

        Returns
        -------
        dict:
            Swagger document. None, if we cannot retrieve the document
        """

        swagger = None

        # First check if there is inline swagger
        if self.definition_body:
            swagger = self._read_from_definition_body()

        if not swagger and self.definition_uri:
            # If not, then try to download it from the given URI
            swagger = self._download_swagger(self.definition_uri)

        return swagger

    def _read_from_definition_body(self):
        """
        Read the Swagger document from DefinitionBody. It could either be an inline Swagger dictionary or an
        AWS::Include macro that contains location of the included Swagger. In the later case, we will download and
        parse the Swagger document.

        Returns
        -------
        dict
            Swagger document, if we were able to parse. None, otherwise
        """

        # Let's try to parse it as AWS::Include Transform first. If not, then fall back to assuming the Swagger document
        # was inclined directly into the body
        location = parse_aws_include_transform(self.definition_body)
        if location:
            LOG.debug("Trying to download Swagger from %s", location)
            return self._download_swagger(location)

        # Inline Swagger, just return the contents which should already be a dictionary
        LOG.debug("Detected Inline Swagger definition")
        return self.definition_body

    def _download_swagger(self, location):
        """
        Download the file from given local or remote location and return it

        Parameters
        ----------
        location : str or dict
            Local path or S3 path to Swagger file to download. Consult the ``__init__.py`` documentation for specifics
            on structure of this property.

        Returns
        -------
        dict or None
            Downloaded and parsed Swagger document. None, if unable to download
        """

        if not location:
            return None

        bucket, key, version = self._parse_s3_location(location)
        if bucket and key:
            LOG.debug("Downloading Swagger document from Bucket=%s, Key=%s, Version=%s", bucket, key, version)
            swagger_str = self._download_from_s3(bucket, key, version)
            return yaml_parse(swagger_str)

        if not isinstance(location, str):
            # This is not a string and not a S3 Location dictionary. Probably something invalid
            LOG.debug("Unable to download Swagger file. Invalid location: %s", location)
            return None

        # ``location`` is a string and not a S3 path. It is probably a local path. Let's resolve relative path if any
        filepath = location
        if self.working_dir:
            # Resolve relative paths, if any, with respect to working directory
            filepath = os.path.join(self.working_dir, location)

        if not os.path.exists(filepath):
            LOG.debug("Unable to download Swagger file. File not found at location %s", filepath)
            return None

        LOG.debug("Reading Swagger document from local file at %s", filepath)
        with open(filepath, "r") as fp:
            return yaml_parse(fp.read())

    @staticmethod
    def _download_from_s3(bucket, key, version=None):
        """
        Download a file from given S3 location, if available.

        Parameters
        ----------
        bucket : str
            S3 Bucket name

        key : str
            S3 Bucket Key aka file path

        version : str
            Optional Version ID of the file

        Returns
        -------
        str
            Contents of the file that was downloaded

        Raises
        ------
        botocore.exceptions.ClientError if we were unable to download the file from S3
        """

        s3 = boto3.client("s3")

        extra_args = {}
        if version:
            extra_args["VersionId"] = version

        with tempfile.TemporaryFile() as fp:
            try:
                s3.download_fileobj(bucket, key, fp, ExtraArgs=extra_args)

                # go to start of file
                fp.seek(0)

                # Read and return all the contents
                return fp.read()

            except botocore.exceptions.ClientError:
                LOG.error(
                    "Unable to download Swagger document from S3 Bucket=%s Key=%s Version=%s", bucket, key, version
                )
                raise

    @staticmethod
    def _parse_s3_location(location):
        """
        Parses the given location input as a S3 Location and returns the file's bucket, key and version as separate
        values. Input can be in two different formats:

        1. Dictionary with ``Bucket``, ``Key``, ``Version`` keys
        2. String of S3 URI in format ``s3://<bucket>/<key>?versionId=<version>``

        If the input is not in either of the above formats, this method will return (None, None, None) tuple for all
        the values.

        Parameters
        ----------
        location : str or dict
            Location of the S3 file

        Returns
        -------
        str
            Name of the S3 Bucket. None, if bucket value was not found
        str
            Key of the file from S3. None, if key was not provided
        str
            Optional Version ID of the file. None, if version ID is not provided
        """

        bucket, key, version = None, None, None
        if isinstance(location, dict):
            # This is a S3 Location dictionary. Just grab the fields. It is very well possible that
            # this dictionary has none of the fields we expect. Return None if the fields don't exist.
            bucket, key, version = (location.get("Bucket"), location.get("Key"), location.get("Version"))

        elif isinstance(location, str) and location.startswith("s3://"):
            # This is a S3 URI. Parse it using a standard URI parser to extract the components

            parsed = urlparse(location)
            query = parse_qs(parsed.query)

            bucket = parsed.netloc
            key = parsed.path.lstrip("/")  # Leading '/' messes with S3 APIs. Remove it.

            # If there is a query string that has a single versionId field,
            # set the object version and return
            if query and "versionId" in query and len(query["versionId"]) == 1:
                version = query["versionId"][0]

        return bucket, key, version
