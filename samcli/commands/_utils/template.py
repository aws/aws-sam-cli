"""
Utilities to manipulate template
"""

import itertools
import os
import pathlib

import jmespath
import yaml
from botocore.utils import set_value_from_jmespath

from samcli.commands.exceptions import UserException
from samcli.lib.samlib.resource_metadata_normalizer import ASSET_PATH_METADATA_KEY, ResourceMetadataNormalizer
from samcli.lib.utils import graphql_api
from samcli.lib.utils.packagetype import IMAGE, ZIP
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_GRAPHQLAPI,
    METADATA_WITH_LOCAL_PATHS,
    RESOURCES_WITH_LOCAL_PATHS,
    get_packageable_resource_paths,
)
from samcli.yamlhelper import yaml_dump, yaml_parse

# Fn::ForEach structure requires exactly 3 elements: [loop_variable, collection, output_template]
FOREACH_REQUIRED_ELEMENTS = 3


class TemplateNotFoundException(UserException):
    pass


class TemplateFailedParsingException(UserException):
    pass


def get_template_data(template_file):
    """
    Read the template file, parse it as JSON/YAML and return the template as a dictionary.

    Parameters
    ----------
    template_file : string
        Path to the template to read

    Returns
    -------
    Template data as a dictionary
    """

    if not pathlib.Path(template_file).exists():
        raise TemplateNotFoundException("Template file not found at {}".format(template_file))

    with open(template_file, "r", encoding="utf-8") as fp:
        try:
            return yaml_parse(fp.read())
        except (ValueError, yaml.YAMLError) as ex:
            raise TemplateFailedParsingException("Failed to parse template: {}".format(str(ex))) from ex


def move_template(src_template_path, dest_template_path, template_dict):
    """
    Move the SAM/CloudFormation template from ``src_template_path`` to ``dest_template_path``. For convenience, this
    method accepts a dictionary of template data ``template_dict`` that will be written to the destination instead of
    reading from the source file.

    SAM/CloudFormation template can contain certain properties whose value is a relative path to a local file/folder.
    This path is always relative to the template's location. Before writing the template to ``dest_template_path`,
    we will update these paths to be relative to the new location.

    This methods updates resource properties supported by ``aws cloudformation package`` command:
    https://docs.aws.amazon.com/cli/latest/reference/cloudformation/package.html

    You must use this method if you are reading a template from one location, modifying it, and writing it back to a
    different location.

    Parameters
    ----------
    src_template_path : str
        Path to the original location of the template

    dest_template_path : str
        Path to the destination location where updated template should be written to

    template_dict : dict
        Dictionary containing template contents. This dictionary will be updated & written to ``dest`` location.
    """

    original_root = os.path.dirname(src_template_path)
    new_root = os.path.dirname(dest_template_path)

    # Next up, we will be writing the template to a different location. Before doing so, we should
    # update any relative paths in the template to be relative to the new location.
    modified_template = _update_relative_paths(template_dict, original_root, new_root)

    # if a stack only has image functions, the directory for that directory won't be created.
    # here we make sure the directory the destination template file to write to exists.
    os.makedirs(os.path.dirname(dest_template_path), exist_ok=True)
    with open(dest_template_path, "w") as fp:
        fp.write(yaml_dump(modified_template))


def _update_relative_paths(template_dict, original_root, new_root):
    """
    SAM/CloudFormation template can contain certain properties whose value is a relative path to a local file/folder.
    This path is usually relative to the template's location. If the template is being moved from original location
    ``original_root`` to new location ``new_root``, use this method to update these paths to be
    relative to ``new_root``.

    After this method is complete, it is safe to write the template to ``new_root`` without
    breaking any relative paths.

    This methods updates resource properties supported by ``aws cloudformation package`` command:
    https://docs.aws.amazon.com/cli/latest/reference/cloudformation/package.html

    If a property is either an absolute path or a S3 URI, this method will not update them.


    Parameters
    ----------
    template_dict : dict
        Dictionary containing template contents. This dictionary will be updated & written to ``dest`` location.

    original_root : str
        Path to the directory where all paths were originally set relative to. This is usually the directory
        containing the template originally

    new_root : str
        Path to the new directory that all paths set relative to after this method completes.

    Returns
    -------
    Updated dictionary

    """

    for resource_type, properties in template_dict.get("Metadata", {}).items():
        if resource_type not in METADATA_WITH_LOCAL_PATHS:
            # Unknown resource. Skipping
            continue

        for path_prop_name in METADATA_WITH_LOCAL_PATHS[resource_type]:
            path = properties.get(path_prop_name)

            updated_path = _resolve_relative_to(path, original_root, new_root)
            if not updated_path:
                # This path does not need to get updated
                continue

            properties[path_prop_name] = updated_path

    for resource_key, resource in template_dict.get("Resources", {}).items():
        # Handle Fn::ForEach blocks - update paths inside them
        if resource_key.startswith("Fn::ForEach::"):
            _update_foreach_relative_paths(resource, original_root, new_root)
            continue

        if not isinstance(resource, dict):
            continue

        resource_type = resource.get("Type")

        if resource_type not in RESOURCES_WITH_LOCAL_PATHS:
            # Unknown resource. Skipping
            continue

        for path_prop_name in RESOURCES_WITH_LOCAL_PATHS[resource_type]:
            properties = resource.get("Properties", {})

            if (
                resource_type in [AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION]
                and properties.get("PackageType", ZIP) == IMAGE
            ):
                if not properties.get("ImageUri"):
                    continue
                resolved_image_archive_path = _resolve_relative_to(properties.get("ImageUri"), original_root, new_root)
                if not resolved_image_archive_path or not pathlib.Path(resolved_image_archive_path).is_file():
                    continue

            # SAM GraphQLApi has many instances of CODE_ARTIFACT_PROPERTY and all of them must be updated
            if resource_type == AWS_SERVERLESS_GRAPHQLAPI and path_prop_name == graphql_api.CODE_ARTIFACT_PROPERTY:
                # to be able to set different nested properties to S3 uri, paths are necessary
                # jmespath doesn't provide that functionality, thus custom implementation
                paths_values = graphql_api.find_all_paths_and_values(path_prop_name, properties)
                for property_path, property_value in paths_values:
                    updated_path = _resolve_relative_to(property_value, original_root, new_root)
                    if not updated_path:
                        # This path does not need to get updated
                        continue
                    set_value_from_jmespath(properties, property_path, updated_path)

            path = jmespath.search(path_prop_name, properties)
            updated_path = _resolve_relative_to(path, original_root, new_root)

            if not updated_path:
                # This path does not need to get updated
                continue

            set_value_from_jmespath(properties, path_prop_name, updated_path)

        metadata = resource.get("Metadata", {})
        if ASSET_PATH_METADATA_KEY in metadata:
            path = metadata.get(ASSET_PATH_METADATA_KEY, "")
            updated_path = _resolve_relative_to(path, original_root, new_root)
            if not updated_path:
                # This path does not need to get updated
                continue
            metadata[ASSET_PATH_METADATA_KEY] = updated_path

    # Update relative paths in SAM-generated Mappings sections.
    # When sam build generates Mappings for dynamic artifact properties (e.g., SAMCodeUriFunctions),
    # the values are relative paths to build artifacts. These paths need to be adjusted when the
    # template is moved from the source directory to the build output directory.
    _update_sam_mappings_relative_paths(template_dict.get("Mappings", {}), original_root, new_root)

    # AWS::Includes can be anywhere within the template dictionary. Hence we need to recurse through the
    # dictionary in a separate method to find and update relative paths in there
    template_dict = _update_aws_include_relative_path(template_dict, original_root, new_root)

    return template_dict


def _update_foreach_relative_paths(foreach_value, original_root, new_root):
    """
    Update relative paths in resources defined inside a Fn::ForEach block.

    Fn::ForEach structure: [loop_variable, collection, output_template]
    The output_template contains resource definitions that may have relative paths.

    This function handles nested Fn::ForEach blocks recursively.

    Parameters
    ----------
    foreach_value : list
        The value of the Fn::ForEach block (should be a list with 3 elements)
    original_root : str
        Path to the directory where all paths were originally set relative to
    new_root : str
        Path to the new directory that all paths set relative to after this method completes
    """
    if not isinstance(foreach_value, list) or len(foreach_value) < FOREACH_REQUIRED_ELEMENTS:
        return

    # The third element is the output template containing resource definitions
    output_template = foreach_value[2]
    if not isinstance(output_template, dict):
        return

    # Check each resource definition in the output template
    for resource_key, resource_def in output_template.items():
        # Handle nested Fn::ForEach blocks recursively
        if resource_key.startswith("Fn::ForEach::"):
            _update_foreach_relative_paths(resource_def, original_root, new_root)
            continue

        if not isinstance(resource_def, dict):
            continue

        resource_type = resource_def.get("Type")
        if resource_type not in RESOURCES_WITH_LOCAL_PATHS:
            continue

        for path_prop_name in RESOURCES_WITH_LOCAL_PATHS[resource_type]:
            properties = resource_def.get("Properties", {})

            if (
                resource_type in [AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION]
                and properties.get("PackageType", ZIP) == IMAGE
            ):
                if not properties.get("ImageUri"):
                    continue
                resolved_image_archive_path = _resolve_relative_to(properties.get("ImageUri"), original_root, new_root)
                if not resolved_image_archive_path or not pathlib.Path(resolved_image_archive_path).is_file():
                    continue

            # SAM GraphQLApi has many instances of CODE_ARTIFACT_PROPERTY and all of them must be updated
            if resource_type == AWS_SERVERLESS_GRAPHQLAPI and path_prop_name == graphql_api.CODE_ARTIFACT_PROPERTY:
                paths_values = graphql_api.find_all_paths_and_values(path_prop_name, properties)
                for property_path, property_value in paths_values:
                    updated_path = _resolve_relative_to(property_value, original_root, new_root)
                    if not updated_path:
                        continue
                    set_value_from_jmespath(properties, property_path, updated_path)

            path = jmespath.search(path_prop_name, properties)
            updated_path = _resolve_relative_to(path, original_root, new_root)

            if not updated_path:
                continue

            set_value_from_jmespath(properties, path_prop_name, updated_path)

        metadata = resource_def.get("Metadata", {})
        if ASSET_PATH_METADATA_KEY in metadata:
            path = metadata.get(ASSET_PATH_METADATA_KEY, "")
            updated_path = _resolve_relative_to(path, original_root, new_root)
            if not updated_path:
                continue
            metadata[ASSET_PATH_METADATA_KEY] = updated_path


def _update_sam_mappings_relative_paths(mappings, original_root, new_root):
    """
    Update relative paths in SAM-generated Mappings sections.

    When sam build generates Mappings for dynamic artifact properties (e.g., Fn::ForEach
    with dynamic CodeUri), the Mapping values contain relative paths to build artifacts.
    These paths need to be adjusted when the template is moved from the source directory
    to the build output directory.

    SAM-generated Mappings follow the naming convention SAM{PropertyName}{LoopName}
    (e.g., SAMCodeUriFunctions). Each entry maps a collection value to a dict containing
    the artifact property name and its path value.

    Parameters
    ----------
    mappings : dict
        The Mappings section of the template (will be modified in place)
    original_root : str
        Path to the directory where all paths were originally set relative to
    new_root : str
        Path to the new directory that all paths set relative to after this method completes
    """
    # Only these property names in SAM-generated Mappings represent local file paths
    # that need relative path adjustment. Other properties (like LayerOutputKey for
    # auto dependency layer references) are CloudFormation references, not file paths.
    _ARTIFACT_PATH_PROPERTIES = {
        "CodeUri",
        "ImageUri",
        "ContentUri",
        "Content",
        "DefinitionUri",
        "BodyS3Location",
        "DefinitionS3Location",
        "SchemaUri",
        "TemplateURL",
        "Location",
    }

    if not isinstance(mappings, dict):
        return

    for mapping_name, mapping_entries in mappings.items():
        # Only process SAM-generated Mappings (prefixed with "SAM")
        if not mapping_name.startswith("SAM"):
            continue

        if not isinstance(mapping_entries, dict):
            continue

        for _key, value_dict in mapping_entries.items():
            if not isinstance(value_dict, dict):
                continue

            for prop_name, prop_value in value_dict.items():
                if prop_name not in _ARTIFACT_PATH_PROPERTIES:
                    continue
                updated_path = _resolve_relative_to(prop_value, original_root, new_root)
                if not updated_path:
                    continue

                # For ImageUri properties, only update if the resolved path points to
                # an actual local file (e.g., a .tar.gz image archive). Docker image
                # references like "my-image:latest" are not local paths and should not
                # be rewritten with relative path prefixes.
                if prop_name == "ImageUri" and not pathlib.Path(updated_path).is_file():
                    continue

                value_dict[prop_name] = updated_path


def _update_aws_include_relative_path(template_dict, original_root, new_root):
    """
    Update relative paths in "AWS::Include" directive. This directive can be present at any part of the template,
    and not just within resources.
    """

    for key, val in template_dict.items():
        if key == "Fn::Transform":
            if isinstance(val, dict) and val.get("Name") == "AWS::Include":
                path = val.get("Parameters", {}).get("Location", {})
                updated_path = _resolve_relative_to(path, original_root, new_root)
                if not updated_path:
                    # This path does not need to get updated
                    continue

                val["Parameters"]["Location"] = updated_path

        # Recurse through all dictionary values
        elif isinstance(val, dict):
            _update_aws_include_relative_path(val, original_root, new_root)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _update_aws_include_relative_path(item, original_root, new_root)

    return template_dict


def _resolve_relative_to(path, original_root, new_root):
    """
    If the given ``path`` is a relative path, then assume it is relative to ``original_root``. This method will
    update the path to be resolve it relative to ``new_root`` and return.

    Examples
    -------
        # Assume a file called template.txt at location /tmp/original/root/template.txt expressed as relative path
        # We are trying to update it to be relative to /tmp/new/root instead of the /tmp/original/root
        >>> result = _resolve_relative_to("template.txt",  \
                                          "/tmp/original/root", \
                                          "/tmp/new/root")
        >>> result
        ../../original/root/template.txt

    Returns
    -------
    Updated path if the given path is a relative path. None, if the path is not a relative path.
    """

    if (
        not isinstance(path, str)
        or path.startswith("s3://")
        or path.startswith("http://")
        or path.startswith("https://")
        or os.path.isabs(path)
    ):
        # Value is definitely NOT a relative path. It is either a S3 URi or Absolute path or not a string at all
        return None

    # Value is definitely a relative path. Change it relative to the destination directory
    return os.path.relpath(
        # Resolve the paths to take care of symlinks
        os.path.normpath(os.path.join(pathlib.Path(original_root).resolve(), path)),
        pathlib.Path(new_root).resolve(),  # Absolute original path w.r.t ``original_root``
    )  # Resolve the original path with respect to ``new_root``


def get_template_parameters(template_file):
    """
    Get Parameters from a template file.

    Parameters
    ----------
    template_file : string
        Path to the template to read

    Returns
    -------
    Template Parameters as a dictionary
    """
    template_dict = get_template_data(template_file=template_file)
    ResourceMetadataNormalizer.normalize(template_dict, True)
    return template_dict.get("Parameters", dict())


def get_template_artifacts_format(template_file):
    """
    Get a list of template artifact formats based on PackageType wherever the underlying resource
    have the actual need to be packaged.
    :param template_file:
    :return: list of artifact formats
    """

    template_dict = get_template_data(template_file=template_file)

    # Get a list of Resources where the artifacts format matter for packaging.
    packageable_resources = get_packageable_resource_paths()

    artifacts = []
    for resource_key, resource in template_dict.get("Resources", {}).items():
        # Handle Fn::ForEach blocks - look inside them for resources
        if resource_key.startswith("Fn::ForEach::"):
            foreach_artifacts = _get_artifacts_from_foreach(resource, packageable_resources)
            artifacts.extend(foreach_artifacts)
            continue

        if not isinstance(resource, dict):
            continue

        # First check if the resources are part of package-able resource types.
        if resource.get("Type") in packageable_resources.keys():
            # Flatten list of locations per resource type.
            locations = list(itertools.chain(*packageable_resources.get(resource.get("Type"))))
            for location in locations:
                properties = resource.get("Properties", {})
                # Search for package-able location within resource properties.
                if jmespath.search(location, properties):
                    artifacts.append(properties.get("PackageType", ZIP))

    return artifacts


def _get_artifacts_from_foreach(foreach_value, packageable_resources):
    """
    Extract artifact formats from resources defined inside a Fn::ForEach block.

    Fn::ForEach structure: [loop_variable, collection, output_template]
    The output_template contains resource definitions that will be expanded.

    This function handles nested Fn::ForEach blocks recursively.

    :param foreach_value: The value of the Fn::ForEach block (should be a list with 3 elements)
    :param packageable_resources: Dict of packageable resource types and their paths
    :return: list of artifact formats found in the ForEach block
    """
    artifacts = []

    if not isinstance(foreach_value, list) or len(foreach_value) < FOREACH_REQUIRED_ELEMENTS:
        return artifacts

    # The third element is the output template containing resource definitions
    output_template = foreach_value[2]
    if not isinstance(output_template, dict):
        return artifacts

    # Check each resource definition in the output template
    for resource_key, resource_def in output_template.items():
        # Handle nested Fn::ForEach blocks recursively
        if resource_key.startswith("Fn::ForEach::"):
            nested_artifacts = _get_artifacts_from_foreach(resource_def, packageable_resources)
            artifacts.extend(nested_artifacts)
            continue

        if not isinstance(resource_def, dict):
            continue

        resource_type = resource_def.get("Type")
        if resource_type in packageable_resources.keys():
            # Flatten list of locations per resource type
            locations = list(itertools.chain(*packageable_resources.get(resource_type)))
            for location in locations:
                properties = resource_def.get("Properties", {})
                # Search for package-able location within resource properties
                if jmespath.search(location, properties):
                    artifacts.append(properties.get("PackageType", ZIP))

    return artifacts


def get_template_function_resource_ids(template_file, artifact):
    """
    Get a list of function logical ids from template file.
    Function resource types include
        AWS::Lambda::Function
        AWS::Serverless::Function
    :param template_file: template file location.
    :param artifact: artifact of type IMAGE or ZIP
    :return: list of artifact formats
    """

    template_dict = get_template_data(template_file=template_file)
    _function_resource_ids = []
    for resource_id, resource in template_dict.get("Resources", {}).items():
        # Handle Fn::ForEach blocks - look inside them for function resources
        # Note: We can't return the actual expanded resource IDs here since we don't
        # have the collection values resolved. We return a placeholder to indicate
        # that functions exist inside the ForEach block.
        if resource_id.startswith("Fn::ForEach::"):
            foreach_functions = _get_function_ids_from_foreach(resource, artifact)
            if foreach_functions:
                # Return the ForEach key as a placeholder - the actual function IDs
                # will be determined after language extensions are processed
                _function_resource_ids.append(resource_id)
            continue

        if not isinstance(resource, dict):
            continue
        if resource.get("Properties", {}).get("PackageType", ZIP) == artifact and resource.get("Type") in [
            AWS_SERVERLESS_FUNCTION,
            AWS_LAMBDA_FUNCTION,
        ]:
            _function_resource_ids.append(resource_id)
    return _function_resource_ids


def _get_function_ids_from_foreach(foreach_value, artifact):
    """
    Check if a Fn::ForEach block contains function resources with the specified artifact type.

    This function handles nested Fn::ForEach blocks recursively.

    :param foreach_value: The value of the Fn::ForEach block (should be a list with 3 elements)
    :param artifact: artifact of type IMAGE or ZIP
    :return: list of resource template keys that are functions (not expanded IDs)
    """
    function_keys = []

    if not isinstance(foreach_value, list) or len(foreach_value) < FOREACH_REQUIRED_ELEMENTS:
        return function_keys

    # The third element is the output template containing resource definitions
    output_template = foreach_value[2]
    if not isinstance(output_template, dict):
        return function_keys

    # Check each resource definition in the output template
    for resource_key, resource_def in output_template.items():
        # Handle nested Fn::ForEach blocks recursively
        if resource_key.startswith("Fn::ForEach::"):
            nested_functions = _get_function_ids_from_foreach(resource_def, artifact)
            function_keys.extend(nested_functions)
            continue

        if not isinstance(resource_def, dict):
            continue

        resource_type = resource_def.get("Type")
        package_type = resource_def.get("Properties", {}).get("PackageType", ZIP)

        if package_type == artifact and resource_type in [AWS_SERVERLESS_FUNCTION, AWS_LAMBDA_FUNCTION]:
            function_keys.append(resource_key)

    return function_keys
