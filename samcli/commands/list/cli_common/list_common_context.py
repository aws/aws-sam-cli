"""
Common context class to inherit from for sam list sub-commands
"""

from samcli.lib.utils.boto_utils import get_boto_client_provider_with_config


class ListContext:
    def __init__(self):
        self.cloudformation_client = None
        self.client_provider = None
        self.region = None
        self.profile = None

    def init_clients(self) -> None:
        """
        Initialize the clients being used by sam list.
        """
        from boto3 import Session

        if not self.region:
            session = Session()
            self.region = session.region_name

        client_provider = get_boto_client_provider_with_config(region=self.region, profile=self.profile)
        self.client_provider = client_provider
        self.cloudformation_client = client_provider("cloudformation")
