"""
SAM CLI Default Build constants
"""

import os

DEFAULT_STACK_NAME = "sam-app"
DEFAULT_BUILD_DIR = os.path.join(".aws-sam", "build")
DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER = os.path.join(".aws-sam", "auto-dependency-layer")
DEFAULT_CACHE_DIR = os.path.join(".aws-sam", "cache")
DEFAULT_BUILT_TEMPLATE_PATH = os.path.join(".aws-sam", "build", "template.yaml")

# Template file names SAM CLI recognises, in resolution order. Must stay in the same order as
# the search used by get_or_default_template_file_name, so that a template path reported by one
# command is the one another command would resolve to.
SAM_TEMPLATE_FILE_NAMES = ["template.yaml", "template.yml", "template.json"]
