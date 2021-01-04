"""
Enums for Resources and thier Location Properties, along with utility functions
"""

from collections import defaultdict

AWS_SERVERLESSREPO_APPLICATION = "AWS::ServerlessRepo::Application"
AWS_SERVERLESS_FUNCTION = "AWS::Serverless::Function"
AWS_SERVERLESS_API = "AWS::Serverless::Api"
AWS_SERVERLESS_HTTPAPI = "AWS::Serverless::HttpApi"
AWS_APPSYNC_GRAPHQLSCHEMA = "AWS::AppSync::GraphQLSchema"
AWS_APPSYNC_RESOLVER = "AWS::AppSync::Resolver"
AWS_APPSYNC_FUNCTIONCONFIGURATION = "AWS::AppSync::FunctionConfiguration"
AWS_LAMBDA_FUNCTION = "AWS::Lambda::Function"
AWS_APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
AWS_ELASTICBEANSTALK_APPLICATIONVERSION = "AWS::ElasticBeanstalk::ApplicationVersion"
AWS_CLOUDFORMATION_STACK = "AWS::CloudFormation::Stack"
AWS_SERVERLESS_APPLICATION = "AWS::Serverless::Application"
AWS_LAMBDA_LAYERVERSION = "AWS::Lambda::LayerVersion"
AWS_SERVERLESS_LAYERVERSION = "AWS::Serverless::LayerVersion"
AWS_GLUE_JOB = "AWS::Glue::Job"
AWS_SERVERLESS_STATEMACHINE = "AWS::Serverless::StateMachine"
AWS_STEPFUNCTIONS_STATEMACHINE = "AWS::StepFunctions::StateMachine"

METADATA_WITH_LOCAL_PATHS = {AWS_SERVERLESSREPO_APPLICATION: ["LicenseUrl", "ReadmeUrl"]}

RESOURCES_WITH_LOCAL_PATHS = {
    AWS_SERVERLESS_FUNCTION: ["CodeUri"],
    AWS_SERVERLESS_API: ["DefinitionUri"],
    AWS_SERVERLESS_HTTPAPI: ["DefinitionUri"],
    AWS_SERVERLESS_STATEMACHINE: ["DefinitionUri"],
    AWS_APPSYNC_GRAPHQLSCHEMA: ["DefinitionS3Location"],
    AWS_APPSYNC_RESOLVER: ["RequestMappingTemplateS3Location", "ResponseMappingTemplateS3Location"],
    AWS_APPSYNC_FUNCTIONCONFIGURATION: ["RequestMappingTemplateS3Location", "ResponseMappingTemplateS3Location"],
    AWS_LAMBDA_FUNCTION: ["Code"],
    AWS_APIGATEWAY_RESTAPI: ["BodyS3Location"],
    AWS_ELASTICBEANSTALK_APPLICATIONVERSION: ["SourceBundle"],
    AWS_CLOUDFORMATION_STACK: ["TemplateURL"],
    AWS_SERVERLESS_APPLICATION: ["Location"],
    AWS_LAMBDA_LAYERVERSION: ["Content"],
    AWS_SERVERLESS_LAYERVERSION: ["ContentUri"],
    AWS_GLUE_JOB: ["Command.ScriptLocation"],
    AWS_STEPFUNCTIONS_STATEMACHINE: ["DefinitionS3Location"],
}

RESOURCES_WITH_IMAGE_COMPONENT = {
    AWS_SERVERLESS_FUNCTION: ["ImageUri"],
    AWS_LAMBDA_FUNCTION: ["Code"],
}


def resources_generator():
    """
    Generator to yield set of resources and their locations that are supported for package operations
    :return:
    """
    _resource_property_dict = defaultdict(list)
    for _dict in (METADATA_WITH_LOCAL_PATHS, RESOURCES_WITH_LOCAL_PATHS, RESOURCES_WITH_IMAGE_COMPONENT):
        for key, value in _dict.items():
            # Only add values to the list if they are different, same property name could be used with the resource
            # to package to different locations.
            if value not in _resource_property_dict.get(key, []):
                _resource_property_dict[key].append(value)

    for resource, location_list in _resource_property_dict.items():
        for locations in location_list:
            for location in locations:
                yield resource, location
