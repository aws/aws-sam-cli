"""
Terraform hooks implementation
"""

from dataclasses import dataclass
import json
import os
import subprocess
from tempfile import NamedTemporaryFile
from typing import Callable, Dict
from samcli.lib.hook.hooks import Hooks, IacApplicationInfo, IacPrepareParams, IacPrepareOutput
from samcli.lib.utils.hash import str_checksum
from samcli.lib.utils.resources import (
    AWS_LAMBDA_FUNCTION as CFN_AWS_LAMBDA_FUNCTION,
)

TF_AWS_LAMBDA_FUNCTION = "aws_lambda_function"
SUPPORTED_RESOURCE_TYPES = [TF_AWS_LAMBDA_FUNCTION]
PROVIDER_NAME = "registry.terraform.io/hashicorp/aws"

# max logical id len is 255
LOGICAL_ID_HASH_LEN = 8
LOGICAL_ID_MAX_HUMAN_LEN = 247


@dataclass
class Translator:
    cfn_name: str
    translate: Callable[["TerraformHooks", dict], dict]


class TerraformHooks(Hooks):
    def __init__(self):
        pass

    def prepare(self, params: IacPrepareParams) -> IacPrepareOutput:
        try:
            # initialize terraform application
            subprocess.run(["terraform", "init", "-upgrade"], check=True)

            # get json output of terraform plan
            with NamedTemporaryFile() as temp_file:
                subprocess.run(["terraform", "plan", "-out", temp_file.name], check=True)
                result = subprocess.run(["terraform", "show", "-json", temp_file.name], check=True, capture_output=True)
            tf_json = json.loads(result.stdout)

            # convert terraform to cloudformation
            cfn_dict = self._translate_to_cfn(tf_json)

            # store in supplied output dir
            if not os.path.exists(params.OutputDirPath):
                os.mkdir(params.OutputDirPath)
            metadataFilePath = os.path.join(params.OutputDirPath, "template.json")
            with open(metadataFilePath, "w") as metadata_file:
                json.dump(cfn_dict, metadata_file)

            return IacPrepareOutput({"MainApplication": IacApplicationInfo(metadataFilePath)})

        except subprocess.CalledProcessError as e:
            # one of the subprocess.run calls resulted in non-zero exit code
            pass
        except Exception as e:
            # handle other exceptions
            pass

    def _translate_to_cfn(self, tf_json: dict) -> dict:
        root_module = tf_json["planned_values"]["root_module"]  # TODO: could these be None?
        cfn_dict = {"AWSTemplateFormatVersion": "2010-09-09", "Resources": {}}

        # create and iterate over queue of modules to handle child modules
        module_queue = [root_module]
        while module_queue:
            curr_module = module_queue.pop()

            # add child modules, if any, to queue
            child_modules = curr_module.get("child_modules")
            if child_modules:
                module_queue += child_modules

            # iterate over resources for current module
            resources = curr_module.get("resources", {})
            for resource in resources:
                provider = resource.get("provider_name")
                resource_type = resource.get("type")

                # only process if supported
                if provider != PROVIDER_NAME or resource_type not in SUPPORTED_RESOURCE_TYPES:
                    continue

                # translate TF resource "values" to CFN properties
                resource_translator = TerraformHooks.RESOURCE_TRANSLATOR_MAPPING.get(resource_type)
                translated_properties = resource_translator.translate(resource.get("values"))  # TODO: error handling

                # build CFN logical ID from resource address
                resource_address = resource.get("address")
                logical_id = self._build_cfn_logical_id(resource_address)

                # Add resource to cfn dict
                cfn_dict["Resources"][logical_id] = {
                    "Type": resource_translator.cfn_name,
                    "Properties": translated_properties,
                    "Metadata": {"SamResourceId": resource_address, "SkipBuild": True},
                }

        return cfn_dict

    def _translate_aws_lambda_function(self, tf_properties: dict) -> dict:
        cfn_properties = {}
        for tf_prop_name, tf_prop_value in tf_properties.items():
            property_translator = TerraformHooks.AWS_LAMBDA_FUNCTION_PROPERTY_TRANSLATOR_MAPPING.get(tf_prop_name)
            translated_prop_value = property_translator.translate(tf_prop_value)
            cfn_properties[property_translator.cfn_name] = translated_prop_value
        return cfn_properties

    RESOURCE_TRANSLATOR_MAPPING: Dict[str, Translator] = {
        TF_AWS_LAMBDA_FUNCTION: Translator(CFN_AWS_LAMBDA_FUNCTION, _translate_aws_lambda_function),
    }

    def _translate_one_to_one_property(self, tf_prop_value: dict) -> dict:
        return tf_prop_value

    def _translate_lambda_function_environment_property(self, tf_environment: dict) -> dict:
        return {"Variables": tf_environment.get("variables")}

    AWS_LAMBDA_FUNCTION_PROPERTY_TRANSLATOR_MAPPING: Dict[str, Translator] = {
        "function_name": Translator("FunctionName", _translate_one_to_one_property),
        "architectures": Translator("Architectures", _translate_one_to_one_property),
        "environment": Translator("Environment", _translate_lambda_function_environment_property),
        "filename": Translator("Code", _translate_one_to_one_property),
        "handler": Translator("Handler", _translate_one_to_one_property),
        "package_type": Translator("PackageType", _translate_one_to_one_property),
        "runtime": Translator("Runtime", _translate_one_to_one_property),
        "layers": Translator("Layers", _translate_one_to_one_property),
        # TODO: s3 bucket and key
    }

    def _build_cfn_logical_id(self, tf_address: str) -> str:
        # ignores non-alphanumericals, makes uppercase the first alphanumerical char and the
        # alphanumerical char right after a non-alphanumerical char
        chars = []
        nextCharUppercase = True
        for char in tf_address:
            if len(chars) == LOGICAL_ID_MAX_HUMAN_LEN:
                break
            if not char.isalnum():
                nextCharUppercase = True
                continue
            if nextCharUppercase:
                chars.append(char.upper())
                nextCharUppercase = False
            else:
                chars.append(char)

        human_part = "".join(chars)
        hash_part = str_checksum(tf_address)[:LOGICAL_ID_HASH_LEN].upper()

        return human_part + hash_part
