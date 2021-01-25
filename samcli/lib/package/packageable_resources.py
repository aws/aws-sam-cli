"""
Code for all Package-able resources
"""
import logging
import os
import shutil
from typing import Optional, Union, Dict

import jmespath
from botocore.utils import set_value_from_jmespath

from samcli.commands.package import exceptions
from samcli.lib.package.ecr_uploader import ECRUploader
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.uploaders import Destination, Uploaders
from samcli.lib.package.utils import (
    resource_not_packageable,
    is_local_file,
    is_zip_file,
    copy_to_temp_dir,
    upload_local_artifacts,
    upload_local_image_artifacts,
    is_s3_url,
    is_path_value_valid,
)

from samcli.commands._utils.resources import (
    AWS_SERVERLESSREPO_APPLICATION,
    AWS_SERVERLESS_FUNCTION,
    AWS_SERVERLESS_API,
    AWS_SERVERLESS_HTTPAPI,
    AWS_APPSYNC_GRAPHQLSCHEMA,
    AWS_APPSYNC_RESOLVER,
    AWS_APPSYNC_FUNCTIONCONFIGURATION,
    AWS_LAMBDA_FUNCTION,
    AWS_APIGATEWAY_RESTAPI,
    AWS_SERVERLESS_STATEMACHINE,
    AWS_ELASTICBEANSTALK_APPLICATIONVERSION,
    AWS_LAMBDA_LAYERVERSION,
    AWS_SERVERLESS_LAYERVERSION,
    AWS_GLUE_JOB,
    AWS_STEPFUNCTIONS_STATEMACHINE,
    METADATA_WITH_LOCAL_PATHS,
    RESOURCES_WITH_LOCAL_PATHS,
    RESOURCES_WITH_IMAGE_COMPONENT,
)

from samcli.lib.utils.packagetype import IMAGE, ZIP

LOG = logging.getLogger(__name__)


class Resource:
    RESOURCE_TYPE: Optional[str] = None
    PROPERTY_NAME: Optional[str] = None
    PACKAGE_NULL_PROPERTY = True
    # Set this property to True in base class if you want the exporter to zip
    # up the file before uploading This is useful for Lambda functions.
    FORCE_ZIP = False
    EXPORT_DESTINATION: Destination
    ARTIFACT_TYPE: Optional[str] = None

    def __init__(self, uploaders: Uploaders, code_signer):
        self.uploaders = uploaders
        self.code_signer = code_signer

    @property
    def uploader(self) -> Union[S3Uploader, ECRUploader]:
        """
        Return the uploader matching the EXPORT_DESTINATION
        """
        return self.uploaders.get(self.EXPORT_DESTINATION)

    def export(self, resource_id, resource_dict, parent_dir):
        self.do_export(resource_id, resource_dict, parent_dir)

    def do_export(self, resource_id, resource_dict, parent_dir):
        pass


class ResourceZip(Resource):
    """
    Base class representing a CloudFormation resource that can be exported
    """

    RESOURCE_TYPE: Optional[str] = None
    PROPERTY_NAME: Optional[str] = None
    PACKAGE_NULL_PROPERTY = True
    # Set this property to True in base class if you want the exporter to zip
    # up the file before uploading This is useful for Lambda functions.
    FORCE_ZIP = False
    ARTIFACT_TYPE = ZIP
    EXPORT_DESTINATION = Destination.S3

    def export(self, resource_id: str, resource_dict: Optional[Dict], parent_dir: str):
        if resource_dict is None:
            return

        if resource_not_packageable(resource_dict):
            return

        property_value = jmespath.search(self.PROPERTY_NAME, resource_dict)

        if not property_value and not self.PACKAGE_NULL_PROPERTY:
            return

        if isinstance(property_value, dict):
            LOG.debug("Property %s of %s resource is not a URL", self.PROPERTY_NAME, resource_id)
            return

        # If property is a file but not a zip file, place file in temp
        # folder and send the temp folder to be zipped
        temp_dir = None
        if is_local_file(property_value) and not is_zip_file(property_value) and self.FORCE_ZIP:
            temp_dir = copy_to_temp_dir(property_value)
            set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, temp_dir)

        try:
            self.do_export(resource_id, resource_dict, parent_dir)

        except Exception as ex:
            LOG.debug("Unable to export", exc_info=ex)
            raise exceptions.ExportFailedError(
                resource_id=resource_id, property_name=self.PROPERTY_NAME, property_value=property_value, ex=ex
            )
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir)

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        Default export action is to upload artifacts and set the property to
        S3 URL of the uploaded object
        If code signing configuration is provided for function/layer, uploaded artifact
        will be replaced by signed artifact location
        """
        # code signer only accepts files which has '.zip' extension in it
        # so package artifact with '.zip' if it is required to be signed
        should_sign_package = self.code_signer.should_sign_package(resource_id)
        artifact_extension = "zip" if should_sign_package else None
        uploaded_url = upload_local_artifacts(
            resource_id,
            resource_dict,
            self.PROPERTY_NAME,
            parent_dir,
            self.uploader,
            artifact_extension,
        )
        if should_sign_package:
            uploaded_url = self.code_signer.sign_package(
                resource_id, uploaded_url, self.uploader.get_version_of_artifact(uploaded_url)
            )
        set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, uploaded_url)


class ResourceImageDict(Resource):
    """
    Base class representing a CFN Image based resource that can be exported.
    """

    RESOURCE_TYPE: Optional[str] = None
    PROPERTY_NAME: Optional[str] = None
    FORCE_ZIP = False
    ARTIFACT_TYPE = IMAGE
    EXPORT_DESTINATION = Destination.ECR
    EXPORT_PROPERTY_CODE_KEY = "ImageUri"

    def export(self, resource_id, resource_dict, parent_dir):
        if resource_dict is None:
            return

        property_value = jmespath.search(self.PROPERTY_NAME, resource_dict)

        if isinstance(property_value, dict):
            LOG.debug("Property %s of %s resource is not a URL or a local image", self.PROPERTY_NAME, resource_id)
            return

        try:
            self.do_export(resource_id, resource_dict, parent_dir)

        except Exception as ex:
            LOG.debug("Unable to export", exc_info=ex)
            raise exceptions.ExportFailedError(
                resource_id=resource_id, property_name=self.PROPERTY_NAME, property_value=property_value, ex=ex
            )

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        Default export action is to upload artifacts and set the property to
        dictionary where the key is EXPORT_PROPERTY_CODE_KEY and value is set to an
        uploaded URL.
        """
        uploaded_url = upload_local_image_artifacts(
            resource_id, resource_dict, self.PROPERTY_NAME, parent_dir, self.uploader
        )
        set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, {self.EXPORT_PROPERTY_CODE_KEY: uploaded_url})


class ResourceImage(Resource):
    """
    Base class representing a SAM Image based resource that can be exported.
    """

    RESOURCE_TYPE: Optional[str] = None
    PROPERTY_NAME: Optional[str] = None
    FORCE_ZIP = False
    ARTIFACT_TYPE: Optional[str] = IMAGE
    EXPORT_DESTINATION = Destination.ECR

    def export(self, resource_id, resource_dict, parent_dir):
        if resource_dict is None:
            return

        property_value = jmespath.search(self.PROPERTY_NAME, resource_dict)

        if isinstance(property_value, dict):
            LOG.debug("Property %s of %s resource is not a URL or a local image", self.PROPERTY_NAME, resource_id)
            return

        try:
            self.do_export(resource_id, resource_dict, parent_dir)

        except Exception as ex:
            LOG.debug("Unable to export", exc_info=ex)
            raise exceptions.ExportFailedError(
                resource_id=resource_id, property_name=self.PROPERTY_NAME, property_value=property_value, ex=ex
            )

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        Default export action is to upload artifacts and set the property to
        URL of the uploaded object
        """
        uploaded_url = upload_local_image_artifacts(
            resource_id, resource_dict, self.PROPERTY_NAME, parent_dir, self.uploader
        )
        set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, uploaded_url)


class ResourceWithS3UrlDict(ResourceZip):
    """
    Represents CloudFormation resources that need the S3 URL to be specified as
    an dict like {Bucket: "", Key: "", Version: ""}
    """

    BUCKET_NAME_PROPERTY: Optional[str] = None
    OBJECT_KEY_PROPERTY: Optional[str] = None
    VERSION_PROPERTY: Optional[str] = None
    ARTIFACT_TYPE = ZIP
    EXPORT_DESTINATION = Destination.S3

    def do_export(self, resource_id, resource_dict, parent_dir):
        """
        Upload to S3 and set property to an dict representing the S3 url
        of the uploaded object
        """

        artifact_s3_url = upload_local_artifacts(
            resource_id, resource_dict, self.PROPERTY_NAME, parent_dir, self.uploader
        )

        parsed_url = S3Uploader.parse_s3_url(
            artifact_s3_url,
            bucket_name_property=self.BUCKET_NAME_PROPERTY,
            object_key_property=self.OBJECT_KEY_PROPERTY,
            version_property=self.VERSION_PROPERTY,
        )
        set_value_from_jmespath(resource_dict, self.PROPERTY_NAME, parsed_url)


class ServerlessFunctionResource(ResourceZip):
    RESOURCE_TYPE = AWS_SERVERLESS_FUNCTION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    FORCE_ZIP = True


class ServerlessFunctionImageResource(ResourceImage):
    RESOURCE_TYPE = AWS_SERVERLESS_FUNCTION
    PROPERTY_NAME = RESOURCES_WITH_IMAGE_COMPONENT[RESOURCE_TYPE][0]
    FORCE_ZIP = False


class ServerlessApiResource(ResourceZip):
    RESOURCE_TYPE = AWS_SERVERLESS_API
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    # Don't package the directory if DefinitionUri is omitted.
    # Necessary to support DefinitionBody
    PACKAGE_NULL_PROPERTY = False


class ServerlessHttpApiResource(ResourceZip):
    RESOURCE_TYPE = AWS_SERVERLESS_HTTPAPI
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    # Don't package the directory if DefinitionUri is omitted.
    # Necessary to support DefinitionBody
    PACKAGE_NULL_PROPERTY = False


class ServerlessStateMachineResource(ResourceWithS3UrlDict):
    RESOURCE_TYPE = AWS_SERVERLESS_STATEMACHINE
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    PACKAGE_NULL_PROPERTY = False
    BUCKET_NAME_PROPERTY = "Bucket"
    OBJECT_KEY_PROPERTY = "Key"
    VERSION_PROPERTY = "Version"


class GraphQLSchemaResource(ResourceZip):
    RESOURCE_TYPE = AWS_APPSYNC_GRAPHQLSCHEMA
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    # Don't package the directory if DefinitionS3Location is omitted.
    # Necessary to support Definition
    PACKAGE_NULL_PROPERTY = False


class AppSyncResolverRequestTemplateResource(ResourceZip):
    RESOURCE_TYPE = AWS_APPSYNC_RESOLVER
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    # Don't package the directory if RequestMappingTemplateS3Location is omitted.
    # Necessary to support RequestMappingTemplate
    PACKAGE_NULL_PROPERTY = False


class AppSyncResolverResponseTemplateResource(ResourceZip):
    RESOURCE_TYPE = AWS_APPSYNC_RESOLVER
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][1]
    # Don't package the directory if ResponseMappingTemplateS3Location is omitted.
    # Necessary to support ResponseMappingTemplate
    PACKAGE_NULL_PROPERTY = False


class AppSyncFunctionConfigurationRequestTemplateResource(ResourceZip):
    RESOURCE_TYPE = AWS_APPSYNC_FUNCTIONCONFIGURATION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    # Don't package the directory if RequestMappingTemplateS3Location is omitted.
    # Necessary to support RequestMappingTemplate
    PACKAGE_NULL_PROPERTY = False


class AppSyncFunctionConfigurationResponseTemplateResource(ResourceZip):
    RESOURCE_TYPE = AWS_APPSYNC_FUNCTIONCONFIGURATION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][1]
    # Don't package the directory if ResponseMappingTemplateS3Location is omitted.
    # Necessary to support ResponseMappingTemplate
    PACKAGE_NULL_PROPERTY = False


class LambdaFunctionResource(ResourceWithS3UrlDict):
    RESOURCE_TYPE = AWS_LAMBDA_FUNCTION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    BUCKET_NAME_PROPERTY = "S3Bucket"
    OBJECT_KEY_PROPERTY = "S3Key"
    VERSION_PROPERTY = "S3ObjectVersion"
    FORCE_ZIP = True


class LambdaFunctionImageResource(ResourceImageDict):
    RESOURCE_TYPE = AWS_LAMBDA_FUNCTION
    PROPERTY_NAME = RESOURCES_WITH_IMAGE_COMPONENT[RESOURCE_TYPE][0]
    FORCE_ZIP = True


class StepFunctionsStateMachineResource(ResourceWithS3UrlDict):
    RESOURCE_TYPE = AWS_STEPFUNCTIONS_STATEMACHINE
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    PACKAGE_NULL_PROPERTY = False
    BUCKET_NAME_PROPERTY = "Bucket"
    OBJECT_KEY_PROPERTY = "Key"
    VERSION_PROPERTY = "Version"


class ApiGatewayRestApiResource(ResourceWithS3UrlDict):
    RESOURCE_TYPE = AWS_APIGATEWAY_RESTAPI
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    PACKAGE_NULL_PROPERTY = False
    BUCKET_NAME_PROPERTY = "Bucket"
    OBJECT_KEY_PROPERTY = "Key"
    VERSION_PROPERTY = "Version"


class ElasticBeanstalkApplicationVersion(ResourceWithS3UrlDict):
    RESOURCE_TYPE = AWS_ELASTICBEANSTALK_APPLICATIONVERSION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    BUCKET_NAME_PROPERTY = "S3Bucket"
    OBJECT_KEY_PROPERTY = "S3Key"
    VERSION_PROPERTY = None


class LambdaLayerVersionResource(ResourceWithS3UrlDict):
    RESOURCE_TYPE = AWS_LAMBDA_LAYERVERSION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    BUCKET_NAME_PROPERTY = "S3Bucket"
    OBJECT_KEY_PROPERTY = "S3Key"
    VERSION_PROPERTY = "S3ObjectVersion"
    FORCE_ZIP = True


class ServerlessLayerVersionResource(ResourceZip):
    RESOURCE_TYPE = AWS_SERVERLESS_LAYERVERSION
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    FORCE_ZIP = True


class ServerlessRepoApplicationLicense(ResourceZip):
    RESOURCE_TYPE = AWS_SERVERLESSREPO_APPLICATION
    PROPERTY_NAME = METADATA_WITH_LOCAL_PATHS[RESOURCE_TYPE][0]
    PACKAGE_NULL_PROPERTY = False


class ServerlessRepoApplicationReadme(ResourceZip):
    RESOURCE_TYPE = AWS_SERVERLESSREPO_APPLICATION
    PROPERTY_NAME = METADATA_WITH_LOCAL_PATHS[RESOURCE_TYPE][1]
    PACKAGE_NULL_PROPERTY = False


class GlueJobCommandScriptLocationResource(ResourceZip):
    """
    Represents Glue::Job resource.
    """

    RESOURCE_TYPE = AWS_GLUE_JOB
    # Note the PROPERTY_NAME includes a '.' implying it's nested.
    PROPERTY_NAME = RESOURCES_WITH_LOCAL_PATHS[AWS_GLUE_JOB][0]


RESOURCES_EXPORT_LIST = [
    ServerlessFunctionResource,
    ServerlessFunctionImageResource,
    ServerlessApiResource,
    ServerlessHttpApiResource,
    ServerlessStateMachineResource,
    GraphQLSchemaResource,
    AppSyncResolverRequestTemplateResource,
    AppSyncResolverResponseTemplateResource,
    AppSyncFunctionConfigurationRequestTemplateResource,
    AppSyncFunctionConfigurationResponseTemplateResource,
    ApiGatewayRestApiResource,
    StepFunctionsStateMachineResource,
    LambdaFunctionResource,
    LambdaFunctionImageResource,
    ElasticBeanstalkApplicationVersion,
    ServerlessLayerVersionResource,
    LambdaLayerVersionResource,
    GlueJobCommandScriptLocationResource,
]

METADATA_EXPORT_LIST = [ServerlessRepoApplicationReadme, ServerlessRepoApplicationLicense]


def include_transform_export_handler(template_dict, uploader, parent_dir):
    if template_dict.get("Name", None) != "AWS::Include":
        return template_dict

    include_location = template_dict.get("Parameters", {}).get("Location", None)
    if not include_location or not is_path_value_valid(include_location) or is_s3_url(include_location):
        # `include_location` is either empty, or not a string, or an S3 URI
        return template_dict

    # We are confident at this point that `include_location` is a string containing the local path
    abs_include_location = os.path.join(parent_dir, include_location)
    if is_local_file(abs_include_location):
        template_dict["Parameters"]["Location"] = uploader.upload_with_dedup(abs_include_location)
    else:
        raise exceptions.InvalidLocalPathError(
            resource_id="AWS::Include", property_name="Location", local_path=abs_include_location
        )

    return template_dict


GLOBAL_EXPORT_DICT = {"Fn::Transform": include_transform_export_handler}
