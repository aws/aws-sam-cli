"""
Utilities to manipulate template
"""

import yaml

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib

from samcli.yamlhelper import yaml_parse


def get_template_data(template_file):
    """
    Read the template file, parse it as JSON/YAML and return the template as a dictionary.

    :param string template_file: Path to the template to read
    :return dict: Template data as a dictionary
    """

    if not pathlib.Path(template_file).exists():
        raise ValueError("Template file not found at {}".format(template_file))

    with open(template_file, 'r') as fp:
        try:
            return yaml_parse(fp.read())
        except (ValueError, yaml.YAMLError) as ex:
            raise ValueError("Failed to parse template: {}".format(str(ex)))
