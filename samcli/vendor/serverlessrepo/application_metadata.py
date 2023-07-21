"""Module containing class to store SAR application metadata."""

from .exceptions import InvalidApplicationMetadataError


class ApplicationMetadata(object):
    """Class representing SAR metadata."""

    # SAM template SAR metadata properties
    NAME = "Name"
    DESCRIPTION = "Description"
    AUTHOR = "Author"
    SPDX_LICENSE_ID = "SpdxLicenseId"
    LICENSE_BODY = "LicenseBody"
    LICENSE_URL = "LicenseUrl"
    README_BODY = "ReadmeBody"
    README_URL = "ReadmeUrl"
    LABELS = "Labels"
    HOME_PAGE_URL = "HomePageUrl"
    SEMANTIC_VERSION = "SemanticVersion"
    SOURCE_CODE_URL = "SourceCodeUrl"

    def __init__(self, app_metadata):
        """
        Initialize the object given SAR metadata properties.

        :param app_metadata: Dictionary containing SAR metadata properties
        :type app_metadata: dict
        """
        self.template_dict = app_metadata  # save the original template definitions
        self.name = app_metadata.get(self.NAME)
        self.description = app_metadata.get(self.DESCRIPTION)
        self.author = app_metadata.get(self.AUTHOR)
        self.spdx_license_id = app_metadata.get(self.SPDX_LICENSE_ID)
        self.license_body = app_metadata.get(self.LICENSE_BODY)
        self.license_url = app_metadata.get(self.LICENSE_URL)
        self.readme_body = app_metadata.get(self.README_BODY)
        self.readme_url = app_metadata.get(self.README_URL)
        self.labels = app_metadata.get(self.LABELS)
        self.home_page_url = app_metadata.get(self.HOME_PAGE_URL)
        self.semantic_version = app_metadata.get(self.SEMANTIC_VERSION)
        self.source_code_url = app_metadata.get(self.SOURCE_CODE_URL)

    def __eq__(self, other):
        """Return whether two ApplicationMetadata objects are equal."""
        return isinstance(other, type(self)) and self.__dict__ == other.__dict__

    def validate(self, required_props):
        """
        Check if the required application metadata properties have been populated.

        :param required_props: List of required properties
        :type required_props: list
        :return: True, if the metadata is valid
        :raises: InvalidApplicationMetadataError
        """
        missing_props = [p for p in required_props if not getattr(self, p)]
        if missing_props:
            raise InvalidApplicationMetadataError(
                error_message="{} properties not provided".format(", ".join(sorted(missing_props)))
            )

        if self.license_body and self.license_url:
            raise InvalidApplicationMetadataError(error_message="provide either LicenseBody or LicenseUrl")

        if self.readme_body and self.readme_url:
            raise InvalidApplicationMetadataError(error_message="provide either ReadmeBody or ReadmeUrl")

        return True
