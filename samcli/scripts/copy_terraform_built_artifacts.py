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


if __name__ == "__main__":
    # Gather inputs and clean them
    argparser = argparse.ArgumentParser(
        description="Copy built artifacts referenced in a json file "
        "(passed via stdin) matching a search pattern"
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
        help="directory to which extracted expression " "contents are copied/unzipped to",
    )

    arguments = argparser.parse_args()
    directory_path = os.path.abspath(arguments.directory)

    if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
        raise OSError("Expected --directory-path to be a valid directory")

    # Load and Parse
    data_object = json.load(sys.stdin)
    output_path = Parser(expression=arguments.expression).parse().search(data=data_object)

    # Check if that is indeed a path.
    if not os.path.exists(output_path):
        raise OSError("Extracted attribute path from provided expression does not exist!")
    filepath = os.path.abspath(output_path)

    # Unzip the zipped file or copy the dir
    try:
        if zipfile.is_zipfile(filepath):
            with zipfile.ZipFile(filepath, "r") as z:
                z.extractall(directory_path)
        else:
            if os.path.isdir(directory_path):
                shutil.copytree(output_path, directory_path, dirs_exist_ok=True)
    except OSError:
        print("Copy/Unzip unsuccessful!")
        sys.exit(1)
