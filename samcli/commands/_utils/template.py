"""
Utilities to manipulate template
"""

import os
import pathlib

import jmespath
import yaml
from botocore.utils import set_value_from_jmespath

from samcli.commands.exceptions import UserException
from samcli.lib.utils.packagetype import ZIP
from samcli.yamlhelper import yaml_parse, yaml_dump
from samcli.commands._utils.resources import (
    METADATA_WITH_LOCAL_PATHS,
    RESOURCES_WITH_LOCAL_PATHS,
    AWS_SERVERLESS_FUNCTION,
    AWS_LAMBDA_FUNCTION,
)


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

    for _, resource in template_dict.get("Resources", {}).items():
        resource_type = resource.get("Type")

        if resource_type not in RESOURCES_WITH_LOCAL_PATHS:
            # Unknown resource. Skipping
            continue

        for path_prop_name in RESOURCES_WITH_LOCAL_PATHS[resource_type]:
            properties = resource.get("Properties", {})

            path = jmespath.search(path_prop_name, properties)
            updated_path = _resolve_relative_to(path, original_root, new_root)

            if not updated_path:
                # This path does not need to get updated
                continue

            set_value_from_jmespath(properties, path_prop_name, updated_path)

    # AWS::Includes can be anywhere within the template dictionary. Hence we need to recurse through the
    # dictionary in a separate method to find and update relative paths in there
    template_dict = _update_aws_include_relative_path(template_dict, original_root, new_root)

    return template_dict


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
        os.path.normpath(os.path.join(original_root, path)), new_root  # Absolute original path w.r.t ``original_root``
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
    return template_dict.get("Parameters", dict())


def get_template_artifacts_format(template_file):
    """
    Get a list of template artifact formats based on PackageType
    :param template_file:
    :return: list of artifact formats
    """

    template_dict = get_template_data(template_file=template_file)
    return list(
        {
            resource_id: resource.get("Properties", {}).get("PackageType", ZIP)
            for resource_id, resource in template_dict.get("Resources", {}).items()
        }.values()
    )


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
        if resource.get("Properties", {}).get("PackageType", ZIP) == artifact and resource.get("Type") in [
            AWS_SERVERLESS_FUNCTION,
            AWS_LAMBDA_FUNCTION,
        ]:
            _function_resource_ids.append(resource_id)
    return _function_resource_ids
