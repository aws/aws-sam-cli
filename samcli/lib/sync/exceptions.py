"""Exceptions related to sync functionalities"""


class MissingPhysicalResourceError(Exception):
    """Exception used for not having a remote/physical counterpart for a local stack resource"""

    _resource_identifier: str

    def __init__(self, resource_identifier: str):
        """
        Parameters
        ----------
        resource_identifier : str
            Logical resource identifier
        """
        super().__init__(f"{resource_identifier} is not found in remote.")
        self._resource_identifier = resource_identifier

    @property
    def resource_identifier(self) -> str:
        """
        Returns
        -------
        str
            Resource identifier of the resource that does not have a remote/physical counterpart
        """
        return self._resource_identifier
