"""
Class for replacing the code uri's in a sam template so that it can be translated
into  CloudFormation yaml template
"""
from samcli.lib.utils.packagetype import ZIP


def _replace_local_codeuri(template):
    """
    Replaces the CodeUri in AWS::Serverless::Function and DefinitionUri in AWS::Serverless::Api and
    AWS::Serverless::HttpApi to a fake S3 Uri. This is to support running the SAM Translator with
    valid values for these fields. If this in not done, the template is invalid in the eyes of SAM
    Translator (the translator does not support local paths)
    """

    all_resources = template.get("Resources", {})
    global_settings = template.get("Globals", {})

    for resource_type, properties in global_settings.items():

        if resource_type == "Function":
            if all(
                [
                    _properties.get("Properties", {}).get("PackageType", ZIP) == ZIP
                    for _, _properties in all_resources.items()
                ]
                + [_properties.get("PackageType", ZIP) == ZIP for _, _properties in global_settings.items()]
            ):
                _update_to_s3_uri("CodeUri", properties)

    for _, resource in all_resources.items():

        resource_type = resource.get("Type")
        resource_dict = resource.get("Properties", {})

        if resource_type == "AWS::Serverless::Function" and resource_dict.get("PackageType", ZIP) == ZIP:

            _update_to_s3_uri("CodeUri", resource_dict)

        if resource_type == "AWS::Serverless::LayerVersion":

            _update_to_s3_uri("ContentUri", resource_dict)

        if resource_type == "AWS::Serverless::Api":
            if "DefinitionUri" in resource_dict:
                _update_to_s3_uri("DefinitionUri", resource_dict)

        if resource_type == "AWS::Serverless::HttpApi":
            if "DefinitionUri" in resource_dict:
                _update_to_s3_uri("DefinitionUri", resource_dict)

        if resource_type == "AWS::Serverless::StateMachine":
            if "DefinitionUri" in resource_dict:
                _update_to_s3_uri("DefinitionUri", resource_dict)

    return template


def is_s3_uri(uri):
    """
    Checks the uri and determines if it is a valid S3 Uri

    Parameters
    ----------
    uri str, required
        Uri to check

    Returns
    -------
    bool
        Returns True if the uri given is an S3 uri, otherwise False

    """
    return isinstance(uri, str) and uri.startswith("s3://")


def _update_to_s3_uri(property_key, resource_property_dict, s3_uri_value="s3://bucket/value"):
    """
    Updates the 'property_key' in the 'resource_property_dict' to the value of 's3_uri_value'

    Note: The function will mutate the resource_property_dict that is pass in

    Parameters
    ----------
    property_key str, required
        Key in the resource_property_dict
    resource_property_dict dict, required
        Property dictionary of a Resource in the template to replace
    s3_uri_value str, optional
        Value to update the value of the property_key to
    """
    uri_property = resource_property_dict.get(property_key, ".")

    # ignore if dict or already an S3 Uri
    if isinstance(uri_property, dict) or is_s3_uri(uri_property):
        return

    resource_property_dict[property_key] = s3_uri_value
