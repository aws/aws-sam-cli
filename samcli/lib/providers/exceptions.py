"""
Exceptions used by providers
"""


class InvalidLayerReference(Exception):
    """
    Raised when the LayerVersion LogicalId does not exist in the template
    """

    def __init__(self) -> None:
        super().__init__(
            "Layer References need to be of type " "'AWS::Serverless::LayerVersion' or 'AWS::Lambda::LayerVersion'"
        )


class RemoteStackLocationNotSupported(Exception):
    pass
