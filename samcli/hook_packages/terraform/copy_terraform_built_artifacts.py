"""
Python script that takes in an expression, input_directory and a json input from the standard input,
tries to find the appropriate element within the json based on the element. It then takes action to
either copy or zip to the specified input_directory.

Note: This script intentionally does not use Python3 specific syntax.
"""

# Sample file:
#
# {
# 	"values": {
# 		"root_module": {
# 			"child_modules": [{
# 				"address": "module_address",
# 				"resources": [{
# 					"address": "sam_metadata_address",
# 					"values": {
# 						"triggers": {
# 							"built_output_path": "/Users/myuser/apps/"
# 						}
# 					}
# 				}]
# 			}]
# 		}
# 	}
# }
#
# Sample Expression:
#
# |values|root_module|child_modules
# [?address=="module_address"]|resources

# pylint: skip-file

import argparse
import re
import os
import json
import shutil
import sys
import zipfile
import logging

from six import string_types

LOG = logging.getLogger(__name__)


class ResolverException(Exception):
    """
    Exception raised by resolver objects
    """

    def __init__(self, message):
        self.message = message
        super(ResolverException, self).__init__(self.message)


class Tokenizer(object):
    """
    Tokenizer class that specifies the delimiter it will be operating on,
    prior to applying to an input_string
    """

    def __init__(self, delimiter=None):
        self.delimiter = delimiter if delimiter else "|"

    def tokenize(self, input_string):
        """
        Tokenizes an input string based on specified delimiter.
        """
        return [token for token in input_string.split(self.delimiter) if token]


class Resolver(object):
    """
    Base Resolver class that exposes a `resolve` method.
    """

    def resolve(self, structured_object):
        """
        returns a portion of the structured_object based on the resolving rules applied.
        """
        raise NotImplementedError


class KeyResolver(Resolver):
    """
    Resolver that operates on a dict structure and matches against a specified condition
    supplied as a key.
    """

    def __init__(self, key):
        self.key = key

    def resolve(self, structured_object):
        if not structured_object or not isinstance(structured_object, dict):
            raise ResolverException("Data object malformed: {}".format(structured_object))
        return structured_object.get(self.key, {})


class ListConditionResolver(Resolver):
    """
    Resolver that operates on a list structure and matches against a specified condition
    supplied as a key, value.
    """

    def __init__(self, key, value):
        self.key = key
        # Remove any quotes from the value
        self.value = value.strip('"')

    def resolve(self, structured_object):
        if not structured_object or not isinstance(structured_object, list):
            raise ResolverException("Data object malformed: {}".format(structured_object))
        for item in structured_object:
            if isinstance(item, dict) and item.get(self.key) == self.value:
                return item
        return {}


class Parser(object):
    """
    Extremely simple parser that relies on a match against a regex
    to see if the given token needs to be mapped to
    a KeyResolver or a ListConditionResolver.
    """

    def __init__(self, expression):
        self.expression = expression
        self.resolvers = []
        # Regex for resolving against a key==value expression within a list.
        self.list_resolver_regex = re.compile(r"\[\?(\S+)==(\S+)\]")
        self.tokens = Tokenizer().tokenize(self.expression)
        for token in self.tokens:
            self.resolvers.append(self.find_resolver(token))

    def parse(self):
        """
        Instantiate a searcher that returns parsed data based on the resolvers.
        :return:
        """
        return Searcher(self.resolvers)

    def find_resolver(self, token):
        """
        Find the resolver for the appropriate token. The implementation of this function
        is a direct match against a regex as the number of uses-case to be supported are less.
        """
        groups = self.list_resolver_regex.findall(token)
        if not groups:
            return KeyResolver(key=token)
        else:
            return ListConditionResolver(key=groups[0][0], value=groups[0][1])


class Searcher(object):
    """
    Searcher class that allows for searching a Jpath against structured data.
    """

    def __init__(self, resolvers):
        self.resolvers = resolvers

    def search(self, data):
        """
        Search by applying all resolvers against structured data.
        """

        for resolver in self.resolvers:
            data = resolver.resolve(data)
        return data


def copytree(src, dst):
    """Modified copytree method
    Note: before python3.8 there is no `dir_exists_ok` argument, therefore
    this function explicitly creates one if it does not exist.
    """
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        src_item = os.path.join(src, item)
        dst_item = os.path.join(dst, item)
        if os.path.isdir(src_item):
            # recursively call itself.
            copytree(src_item, dst_item)
        else:
            shutil.copy2(src_item, dst_item)


def cli_exit():
    """
    Unsuccessful exit code for the script.
    """
    sys.exit(1)


if __name__ == "__main__":
    # Gather inputs and clean them
    argparser = argparse.ArgumentParser(
        description="Copy built artifacts referenced in a json file " "(passed via stdin) matching a search pattern"
    )
    argparser.add_argument(
        "--expression",
        type=str,
        required=True,
        help="Jpath query expression separated by | (delimiter) "
        "and allows for searching within a json object."
        "eg: |values|sub_module|[?address==me]|output",
    )
    argparser.add_argument(
        "--directory",
        type=str,
        required=True,
        help="Directory to which extracted expression " "contents are copied/unzipped to",
    )
    argparser.add_argument(
        "--terraform-project-root",
        type=str,
        required=True,
        default=None,
        help="Extracted expression (path), if relative, will be relative to the provided terraform project root.",
    )

    arguments = argparser.parse_args()
    directory_path = os.path.abspath(arguments.directory)

    terraform_project_root = os.path.abspath(arguments.terraform_project_root)
    extracted_attribute_path = None
    data_object = None

    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        LOG.error("Expected --directory to be a valid directory!")
        cli_exit()
    if not os.path.exists(terraform_project_root) or not os.path.isdir(terraform_project_root):
        LOG.error("Expected --terraform-project-path to be a valid directory!")
        cli_exit()

    # Load and Parse
    try:
        data_object = json.load(sys.stdin)
    except ValueError as ex:
        LOG.error("Parsing JSON from stdin unsuccessful!", exc_info=True)
        cli_exit()

    try:
        extracted_attribute_path = Parser(expression=arguments.expression).parse().search(data=data_object)
    except ResolverException as ex:
        LOG.error(ex.message, exc_info=True)
        cli_exit()

    if not isinstance(extracted_attribute_path, string_types):
        LOG.error("Expected the extracted attribute to be a string")
        cli_exit()
    extracted_attribute_path = str(extracted_attribute_path)

    # Construct an absolute path based on if extracted path is relative or absolute.
    abs_attribute_path = (
        os.path.abspath(os.path.join(terraform_project_root, extracted_attribute_path))
        if not os.path.isabs(extracted_attribute_path)
        else os.path.abspath(extracted_attribute_path)
    )
    if not os.path.exists(abs_attribute_path):
        LOG.error("Extracted attribute path from provided expression does not exist!")
        cli_exit()
    if abs_attribute_path == directory_path:
        LOG.error("Extracted expression path cannot be the same as the supplied directory path")
        cli_exit()

    try:
        if zipfile.is_zipfile(abs_attribute_path):
            with zipfile.ZipFile(abs_attribute_path, "r") as z:
                z.extractall(directory_path)
        else:
            copytree(abs_attribute_path, directory_path)
    except OSError as ex:
        LOG.error("Copy/Unzip unsuccessful!", exc_info=ex)
        cli_exit()
