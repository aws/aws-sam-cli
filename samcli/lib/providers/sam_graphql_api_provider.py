"""Parses SAM given the template"""

import logging

import os
from samcli.lib.providers.cfn_base_api_provider import CfnBaseApiProvider


LOG = logging.getLogger(__name__)


class SamGraphQLApiProvider:
    SERVERLESS_FUNCTION = "AWS::Serverless::Function"
    LAMBDA_FUNCTION = "AWS::Lambda::Function"
    APPSYNC_RESOLVER = "AWS::AppSync::Resolver"
    APPSYNC_DATA_SOURCE = "AWS::AppSync::DataSource"
    APPSYNC_SCHEMA = "AWS::AppSync::GraphQLSchema"
    TYPES = [SERVERLESS_FUNCTION, APPSYNC_RESOLVER, APPSYNC_DATA_SOURCE, APPSYNC_SCHEMA, LAMBDA_FUNCTION]

    _DATA_SOURCE_TYPE = "Type"
    _DATA_SOURCE_TYPE_AWS_LAMBDA = "AWS_LAMBDA"
    _DATA_SOURCE_LAMBDA_CONFIG = "LambdaConfig"
    _DATA_SOURCE_LAMBDA_ARN = "LambdaFunctionArn"
    _RESOLVER_FIELD_NAME = "FieldName"
    _RESOLVER_TYPE = "TypeName"
    _RESOLVER_DATA_SOURCE = "DataSourceName"
    _SCHEMA_LOCATION = "DefinitionS3Location"

    def extract_resources(self, resources, collector, cwd=None):
        """
        Extract the Route Object from a given resource and adds it to the RouteCollector.

        Parameters
        ----------
        resources: dict
            The dictionary containing the different resources within the template

        collector: samcli.commands.local.lib.route_collector.ApiCollector
            Instance of the API collector that where we will save the API information

        cwd : str
            Optional working directory with respect to which we will resolve relative path to Swagger file

        """
        # AWS::Serverless::Function is currently included when parsing of Apis because when SamBaseProvider is run on
        # the template we are creating the implicit apis due to plugins that translate it in the SAM repo,
        # which we later merge with the explicit ones in SamApiProvider.merge_apis. This requires the code to be
        # parsed here and in InvokeContext.
        for logical_id, resource in resources.items():
            resource_type = resource.get(CfnBaseApiProvider.RESOURCE_TYPE)
            if resource_type in [SamGraphQLApiProvider.SERVERLESS_FUNCTION, SamGraphQLApiProvider.LAMBDA_FUNCTION]:
                extract_from_serverless_function(logical_id, resource, collector)
            if resource_type == SamGraphQLApiProvider.APPSYNC_RESOLVER:
                self._extract_from_resolver(logical_id, resource, collector)
            if resource_type == SamGraphQLApiProvider.APPSYNC_DATA_SOURCE:
                self._extract_from_data_source(logical_id, resource, collector)
            if resource_type == SamGraphQLApiProvider.APPSYNC_SCHEMA:
                self._extract_from_schema(logical_id, resource, collector, cwd)

    def _extract_from_resolver(self, logical_id, resolver_resource, collector, cwd=None):
        resource_properties = resolver_resource.get("Properties", {})

        data_source = resource_properties.get(self._RESOLVER_DATA_SOURCE)
        resolver_type = resource_properties.get(self._RESOLVER_TYPE)
        field_name = resource_properties.get(self._RESOLVER_FIELD_NAME)

        # @todo check for other ways of referring to the data source
        data_source_logical_id = data_source.get("Fn::GetAtt")[0]

        collector.add_resolver(resolver_type, field_name, data_source_logical_id)

    def _extract_from_data_source(self, logical_id, data_source_resource, collector, cwd=None):
        resource_properties = data_source_resource.get("Properties", {})
        data_source_type = resource_properties.get(self._DATA_SOURCE_TYPE)
        lambda_config = resource_properties.get(self._DATA_SOURCE_LAMBDA_CONFIG, {})

        if data_source_type != self._DATA_SOURCE_TYPE_AWS_LAMBDA:
            LOG.info(
                "Found data source of type %s, but only type %s is supported",
                data_source_type,
                self._DATA_SOURCE_TYPE_AWS_LAMBDA,
            )
        elif self._DATA_SOURCE_LAMBDA_ARN not in lambda_config:
            LOG.info(
                "Did not find %s in %s, data source will be ignored",
                self._DATA_SOURCE_LAMBDA_ARN,
                self._DATA_SOURCE_LAMBDA_CONFIG,
            )
        else:
            lambda_arn = lambda_config.get(self._DATA_SOURCE_LAMBDA_ARN)
            LOG.debug("Found Lambda ARN %s", lambda_arn)
            lambda_logical_id = lambda_arn.split(":")[-1]

            collector.add_data_source(logical_id, lambda_logical_id)

    def _extract_from_schema(self, logical_id, schema_resource, collector, cwd=None):
        resource_properties = schema_resource.get("Properties", {})
        if self._SCHEMA_LOCATION in resource_properties:
            schema_path = resource_properties[self._SCHEMA_LOCATION]
            schema_full_path = os.path.join(cwd, schema_path)

            collector.add_schema(schema_full_path)


def extract_from_serverless_function(logical_id, function_resource, collector, cwd=None):
    collector.add_function(logical_id)
