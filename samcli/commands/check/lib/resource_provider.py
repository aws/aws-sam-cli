"""
Acquires all resources from template, excluding lambda funcitons and lambda funciton permissions
"""
import os
import tempfile

from samcli.yamlhelper import yaml_dump
from samcli.lib.providers.sam_stack_provider import SamLocalStackProvider

from samcli.commands.check.resources.api_gateway import ApiGateway
from samcli.commands.check.resources.lambda_function import LambdaFunction
from samcli.commands.check.resources.lambda_function_permission import LambdaFunctionPermission
from samcli.commands.check.resources.event_source_mapping import EventSourceMapping
from samcli.commands.check.resources.dynamo_db import DynamoDB
from samcli.commands.check.resources.i_am_role import IAMRole


class ResourceProvider:
    def __init__(self, template):
        self.template = template

    def get_local_stacks(self):
        new_file, path = tempfile.mkstemp()

        local_stacks = None

        try:
            tmp = os.fdopen(new_file, "w")

            tmp.write(yaml_dump(self.template))
            tmp.close()

            local_stacks = SamLocalStackProvider.get_stacks(path)[0][0][4]

        finally:
            os.remove(path)

        return local_stacks

    def get_all_resources(self):

        all_api_gateways = {}
        all_lambda_permissions = {}
        all_event_source_mappings = {}
        all_dynamoDB_tables = {}
        all_lambda_functions = {}
        all_iam_roles = {}

        all_resources = {
            "ApiGateways": all_api_gateways,
            "LambdaFunctions": all_lambda_functions,
            "LambdaPermissions": all_lambda_permissions,
            "EventSourceMappings": all_event_source_mappings,
            "DynamoDBTables": all_dynamoDB_tables,
            "IAMRoles": all_iam_roles,
        }

        local_stacks = self.get_local_stacks()

        resources = local_stacks["Resources"]

        for resource_name, resource_obj in resources.items():

            if resource_obj["Type"] == "AWS::ApiGateway::RestApi":
                all_api_gateways[resource_name] = ApiGateway(resource_obj, resource_obj["Type"], resource_name)
            elif resource_obj["Type"] == "AWS::Lambda::Function":
                all_lambda_functions[resource_name] = LambdaFunction(resource_obj, resource_obj["Type"], resource_name)
            elif resource_obj["Type"] == "AWS::Lambda::Permission":
                all_lambda_permissions[resource_name] = LambdaFunctionPermission(
                    resource_obj, resource_obj["Type"], resource_name
                )
            elif resource_obj["Type"] == "AWS::Lambda::EventSourceMapping":
                all_event_source_mappings[resource_name] = EventSourceMapping(
                    resource_obj, resource_obj["Type"], resource_name
                )
            elif resource_obj["Type"] == "AWS::DynamoDB::Table":
                all_dynamoDB_tables[resource_name] = DynamoDB(resource_obj, resource_obj["Type"], resource_name)
            elif resource_obj["Type"] == "AWS::IAM::Role":
                all_iam_roles[resource_name] = IAMRole(resource_obj, resource_obj["Type"], resource_name)

        return all_resources
