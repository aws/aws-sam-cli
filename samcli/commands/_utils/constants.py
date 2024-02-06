"""
SAM CLI Default Build constants
"""

import os

DEFAULT_STACK_NAME = "sam-app"
DEFAULT_BUILD_DIR = os.path.join(".aws-sam", "build")
DEFAULT_BUILD_DIR_WITH_AUTO_DEPENDENCY_LAYER = os.path.join(".aws-sam", "auto-dependency-layer")
DEFAULT_CACHE_DIR = os.path.join(".aws-sam", "cache")
DEFAULT_BUILT_TEMPLATE_PATH = os.path.join(".aws-sam", "build", "template.yaml")
