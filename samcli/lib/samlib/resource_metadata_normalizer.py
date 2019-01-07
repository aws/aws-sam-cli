"""
Class that Normalizes a Template based on Resource Metadata
"""

RESOURCES_KEY = "Resources"
PROPERTIES_KEY = "Properties"
METADATA_KEY = "Metadata"
ASSET_PATH_METADATA_KEY = "aws:asset:path"
ASSET_PROPERTY_METADATA_KEY = "aws:asset:property"


class ResourceMetadataNormalizer(object):

    @staticmethod
    def normalize(template_dict):
        """
        Normalize all Resources in the template with the Metadata Key on the resource.

        This method will mutate the template

        Parameters
        ----------
        template_dict dict
            Dictionary representing the template

        """
        resources = template_dict.get(RESOURCES_KEY, {})

        for _, resource in resources.items():
            resource_metadata = resource.get(METADATA_KEY, {})
            asset_path = resource_metadata.get(ASSET_PATH_METADATA_KEY)
            asset_property = resource_metadata.get(ASSET_PROPERTY_METADATA_KEY)

            ResourceMetadataNormalizer._replace_property(asset_property, asset_path, resource)

    @staticmethod
    def _replace_property(property_key, property_value, resource):
        """
        Replace a property with an asset on a given resource

        This method will mutate the template

        Parameters
        ----------
        property str
            The property to replace on the resource
        property_value str
            The new value of the property
        resource dict
            Dictionary representing the Resource to change

        """
        if property_value and property_key:
            resource.get(PROPERTIES_KEY, {})[property_key] = property_value
