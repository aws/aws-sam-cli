"""
Exceptions used by providers
"""


class InvalidLayerReference(Exception):
    """ """

    def __init__(self):
        super(InvalidLayerReference, self).__init__(
            "Layer References need to be of type " "'AWS::Serverless::LayerVersion' or 'AWS::Lambda::LayerVersion'"
        )
