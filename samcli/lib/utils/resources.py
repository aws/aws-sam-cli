"""
Enums for Resources and their Location Properties, along with utility functions
"""

from collections import defaultdict

from samcli.lib.utils.graphql_api import CODE_ARTIFACT_PROPERTY, SCHEMA_ARTIFACT_PROPERTY

# Lambda
AWS_SERVERLESS_FUNCTION = "AWS::Serverless::Function"
AWS_SERVERLESS_LAYERVERSION = "AWS::Serverless::LayerVersion"

AWS_LAMBDA_FUNCTION = "AWS::Lambda::Function"
AWS_LAMBDA_LAYERVERSION = "AWS::Lambda::LayerVersion"

# APIGW
AWS_SERVERLESS_API = "AWS::Serverless::Api"
AWS_SERVERLESS_HTTPAPI = "AWS::Serverless::HttpApi"

AWS_APIGATEWAY_RESTAPI = "AWS::ApiGateway::RestApi"
AWS_APIGATEWAY_STAGE = "AWS::ApiGateway::Stage"
AWS_APIGATEWAY_RESOURCE = "AWS::ApiGateway::Resource"
AWS_APIGATEWAY_METHOD = "AWS::ApiGateway::Method"
AWS_APIGATEWAY_DEPLOYMENT = "AWS::ApiGateway::Deployment"
AWS_APIGATEWAY_BASE_PATH_MAPPING = "AWS::ApiGateway::BasePathMapping"
AWS_APIGATEWAY_DOMAIN_NAME = "AWS::ApiGateway::DomainName"
AWS_APIGATEWAY_AUTHORIZER = "AWS::ApiGateway::Authorizer"

AWS_APIGATEWAY_V2_API = "AWS::ApiGatewayV2::Api"
AWS_APIGATEWAY_V2_INTEGRATION = "AWS::ApiGatewayV2::Integration"
AWS_APIGATEWAY_V2_ROUTE = "AWS::ApiGatewayV2::Route"
AWS_APIGATEWAY_V2_STAGE = "AWS::ApiGatewayV2::Stage"
AWS_APIGATEWAY_V2_BASE_PATH_MAPPING = "AWS::ApiGatewayV2::ApiMapping"
AWS_APIGATEWAY_V2_DOMAIN_NAME = "AWS::ApiGatewayV2::DomainName"
AWS_APIGATEWAY_V2_AUTHORIZER = "AWS::ApiGatewayV2::Authorizer"

# SFN
AWS_SERVERLESS_STATEMACHINE = "AWS::Serverless::StateMachine"

AWS_STEPFUNCTIONS_STATEMACHINE = "AWS::StepFunctions::StateMachine"

# Others
AWS_SERVERLESS_APPLICATION = "AWS::Serverless::Application"

AWS_SERVERLESSREPO_APPLICATION = "AWS::ServerlessRepo::Application"
AWS_SERVERLESS_GRAPHQLAPI = "AWS::Serverless::GraphQLApi"
AWS_APPSYNC_GRAPHQLSCHEMA = "AWS::AppSync::GraphQLSchema"
AWS_APPSYNC_RESOLVER = "AWS::AppSync::Resolver"
AWS_APPSYNC_FUNCTIONCONFIGURATION = "AWS::AppSync::FunctionConfiguration"
AWS_ELASTICBEANSTALK_APPLICATIONVERSION = "AWS::ElasticBeanstalk::ApplicationVersion"
AWS_CLOUDFORMATION_MODULEVERSION = "AWS::CloudFormation::ModuleVersion"
AWS_CLOUDFORMATION_RESOURCEVERSION = "AWS::CloudFormation::ResourceVersion"
AWS_CLOUDFORMATION_STACK = "AWS::CloudFormation::Stack"
AWS_CLOUDFORMATION_STACKSET = "AWS::CloudFormation::StackSet"
AWS_GLUE_JOB = "AWS::Glue::Job"
AWS_SQS_QUEUE = "AWS::SQS::Queue"
AWS_KINESIS_STREAM = "AWS::Kinesis::Stream"
AWS_SERVERLESS_STATEMACHINE = "AWS::Serverless::StateMachine"
AWS_STEPFUNCTIONS_STATEMACHINE = "AWS::StepFunctions::StateMachine"
AWS_ECR_REPOSITORY = "AWS::ECR::Repository"
AWS_APPLICATION_INSIGHTS = "AWS::ApplicationInsights::Application"
AWS_RESOURCE_GROUP = "AWS::ResourceGroups::Group"

METADATA_WITH_LOCAL_PATHS = {AWS_SERVERLESSREPO_APPLICATION: ["LicenseUrl", "ReadmeUrl"]}

RESOURCES_WITH_LOCAL_PATHS = {
    AWS_SERVERLESS_GRAPHQLAPI: [SCHEMA_ARTIFACT_PROPERTY, CODE_ARTIFACT_PROPERTY],
    AWS_SERVERLESS_FUNCTION: ["CodeUri"],
    AWS_SERVERLESS_API: ["DefinitionUri"],
    AWS_SERVERLESS_HTTPAPI: ["DefinitionUri"],
    AWS_SERVERLESS_STATEMACHINE: ["DefinitionUri"],
    AWS_APPSYNC_GRAPHQLSCHEMA: ["DefinitionS3Location"],
    AWS_APPSYNC_RESOLVER: [
        "RequestMappingTemplateS3Location",
        "ResponseMappingTemplateS3Location",
        "CodeS3Location",
    ],
    AWS_APPSYNC_FUNCTIONCONFIGURATION: [
        "RequestMappingTemplateS3Location",
        "ResponseMappingTemplateS3Location",
        "CodeS3Location",
    ],
    AWS_LAMBDA_FUNCTION: ["Code"],
    AWS_APIGATEWAY_RESTAPI: ["BodyS3Location"],
    AWS_APIGATEWAY_V2_API: ["BodyS3Location"],
    AWS_ELASTICBEANSTALK_APPLICATIONVERSION: ["SourceBundle"],
    AWS_CLOUDFORMATION_MODULEVERSION: ["ModulePackage"],
    AWS_CLOUDFORMATION_RESOURCEVERSION: ["SchemaHandlerPackage"],
    AWS_CLOUDFORMATION_STACK: ["TemplateURL"],
    AWS_CLOUDFORMATION_STACKSET: ["TemplateURL"],
    AWS_SERVERLESS_APPLICATION: ["Location"],
    AWS_LAMBDA_LAYERVERSION: ["Content"],
    AWS_SERVERLESS_LAYERVERSION: ["ContentUri"],
    AWS_GLUE_JOB: ["Command.ScriptLocation"],
    AWS_STEPFUNCTIONS_STATEMACHINE: ["DefinitionS3Location"],
}

RESOURCES_WITH_IMAGE_COMPONENT = {
    AWS_SERVERLESS_FUNCTION: ["ImageUri"],
    AWS_LAMBDA_FUNCTION: ["Code.ImageUri"],
    AWS_ECR_REPOSITORY: ["RepositoryName"],
}

NESTED_STACKS_RESOURCES = {
    AWS_SERVERLESS_APPLICATION: "Location",
    AWS_CLOUDFORMATION_STACK: "TemplateURL",
}

LAMBDA_LOCAL_RESOURCES = [
    AWS_LAMBDA_FUNCTION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
]

CODE_SYNCABLE_RESOURCES = [
    AWS_SERVERLESS_FUNCTION,
    AWS_LAMBDA_FUNCTION,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_API,
    AWS_APIGATEWAY_RESTAPI,
    AWS_SERVERLESS_HTTPAPI,
    AWS_APIGATEWAY_V2_API,
    AWS_SERVERLESS_STATEMACHINE,
    AWS_STEPFUNCTIONS_STATEMACHINE,
]

SYNCABLE_STACK_RESOURCES = [AWS_SERVERLESS_APPLICATION, AWS_CLOUDFORMATION_STACK]

AWS_LAMBDA_FUNCTION_URL = "AWS::Lambda::Url"


def get_packageable_resource_paths():
    """
    Resource Types with respective Locations that are package-able.

    Returns
    ------
    _resource_property_dict : Dict
        Resource Dictionary containing packageable resource types and their locations as a list.
    """
    _resource_property_dict = defaultdict(list)
    for _dict in (
        METADATA_WITH_LOCAL_PATHS,
        RESOURCES_WITH_LOCAL_PATHS,
        RESOURCES_WITH_IMAGE_COMPONENT,
    ):
        for key, value in _dict.items():
            # Only add values to the list if they are different, same property name could be used with the resource
            # to package to different locations.
            if value not in _resource_property_dict.get(key, []):
                _resource_property_dict[key].append(value)

    return _resource_property_dict


def resources_generator():
    """
    Generator to yield set of resources and their locations that are supported for package operations

    Yields
    ------
    resource : Dict
        The resource dictionary
    location : str
        The location of the resource
    """
    for resource, location_list in get_packageable_resource_paths().items():
        for locations in location_list:
            for location in locations:
                yield resource, location
