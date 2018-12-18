"""
Custom exceptions raised by this local library
"""


class NoApisDefined(Exception):
    """
    Raised when there are no APIs defined in the template
    """
    pass


class OverridesNotWellDefinedError(Exception):
    """
    Raised when the overrides file is invalid
    """
    pass


class InvalidLayerReference(Exception):
    """
    Raised when the LayerVersion LogicalId does not exist in the template
    """
    def __init__(self):
        super(InvalidLayerReference, self).__init__("Layer References need to be of type "
                                                    "'AWS::Serverless::LayerVersion' or 'AWS::Lambda::LayerVersion'")
