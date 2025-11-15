"""
OpenAPI Generator - Extracts OpenAPI specification from SAM templates
"""

import logging
from typing import Dict, List, Optional, Tuple, cast

from samcli.commands.generate.openapi.exceptions import (
    ApiResourceNotFoundException,
    MultipleApiResourcesException,
    NoApiResourcesFoundException,
    OpenApiExtractionException,
    TemplateTransformationException,
)
from samcli.commands.local.lib.swagger.reader import SwaggerReader
from samcli.commands.validate.lib.exceptions import InvalidSamDocumentException
from samcli.lib.translate.sam_template_validator import SamTemplateValidator
from samcli.yamlhelper import yaml_parse

LOG = logging.getLogger(__name__)

# API resource types
SERVERLESS_API = "AWS::Serverless::Api"
SERVERLESS_HTTP_API = "AWS::Serverless::HttpApi"
API_GATEWAY_REST_API = "AWS::ApiGateway::RestApi"
API_GATEWAY_V2_API = "AWS::ApiGatewayV2::Api"

SUPPORTED_API_TYPES = [SERVERLESS_API, SERVERLESS_HTTP_API, API_GATEWAY_REST_API, API_GATEWAY_V2_API]


class OpenApiGenerator:
    """
    Generates OpenAPI specification from SAM template
    """

    def __init__(
        self,
        template_file: str,
        api_logical_id: Optional[str] = None,
        parameter_overrides: Optional[Dict] = None,
        region: Optional[str] = None,
        profile: Optional[str] = None,
    ):
        """
        Initialize OpenAPI generator

        Parameters
        ----------
        template_file : str
            Path to SAM template file
        api_logical_id : str, optional
            Logical ID of API resource to generate OpenAPI for
        parameter_overrides : dict, optional
            Template parameter overrides
        region : str, optional
            AWS region (for intrinsic functions)
        profile : str, optional
            AWS profile
        """
        self.template_file = template_file
        self.api_logical_id = api_logical_id
        self.parameter_overrides = parameter_overrides or {}
        self.region = region
        self.profile = profile

    def generate(self) -> Dict:
        """
        Main generation method - extracts OpenAPI from SAM template

        Returns
        -------
        dict
            OpenAPI document as dictionary

        Raises
        ------
        NoApiResourcesFoundException
            If no API resources found in template
        ApiResourceNotFoundException
            If specified API logical ID not found
        MultipleApiResourcesException
            If multiple APIs found and no logical ID specified
        OpenApiExtractionException
            If OpenAPI extraction fails
        """
        LOG.debug("Starting OpenAPI generation from template: %s", self.template_file)

        # 1. Load and parse template
        template = self._load_template()

        # 2. Find API resources
        api_resources = self._find_api_resources(template)

        # 3. Check if template has implicit API (functions with API events)
        has_implicit_api = self._has_implicit_api(template)

        if not api_resources and not has_implicit_api:
            raise NoApiResourcesFoundException()

        # 4. If explicit API exists, use it
        if api_resources:
            target_api_id, target_api_resource = self._select_api_resource(api_resources)
            LOG.debug("Generating OpenAPI for resource: %s (Type: %s)", target_api_id, target_api_resource.get("Type"))

            # Try to extract existing OpenAPI definition first
            openapi_doc = self._extract_existing_definition(target_api_resource, target_api_id)

            if not openapi_doc:
                LOG.debug("No existing OpenAPI definition found, transforming template")
                openapi_doc = self._generate_from_transformation(template, target_api_id, target_api_resource)
        else:
            # Handle implicit API
            LOG.debug("No explicit API resource found, checking for implicit ServerlessRestApi")
            target_api_id = self.api_logical_id or "ServerlessRestApi"
            openapi_doc = self._generate_implicit_api(template, target_api_id)

        # 5. Validate OpenAPI structure
        if not self._validate_openapi(openapi_doc):
            raise OpenApiExtractionException("Generated OpenAPI document is invalid or empty")

        LOG.debug("Successfully generated OpenAPI document")
        return openapi_doc

    def _load_template(self) -> Dict:
        """
        Load and parse SAM template

        Returns
        -------
        dict
            Parsed template dictionary

        Raises
        ------
        OpenApiExtractionException
            If template cannot be loaded
        """
        try:
            with open(self.template_file, "r") as f:
                template = yaml_parse(f.read())

            if not template or not isinstance(template, dict):
                raise OpenApiExtractionException("Template file is empty or invalid")

            if "Resources" not in template:
                raise OpenApiExtractionException("Template does not contain 'Resources' section")

            return template

        except FileNotFoundError as e:
            raise OpenApiExtractionException(f"Template file not found: {self.template_file}") from e
        except Exception as e:
            raise OpenApiExtractionException(f"Failed to load template: {str(e)}") from e

    def _find_api_resources(self, template: Dict) -> Dict[str, Dict]:
        """
        Find all API resources in template

        Parameters
        ----------
        template : dict
            SAM template dictionary

        Returns
        -------
        dict
            Dictionary of API resources {logical_id: resource_dict}
        """
        api_resources = {}
        resources = template.get("Resources", {})

        for logical_id, resource in resources.items():
            resource_type = resource.get("Type")
            if resource_type in SUPPORTED_API_TYPES:
                api_resources[logical_id] = resource

        LOG.debug("Found %d API resources: %s", len(api_resources), list(api_resources.keys()))
        return api_resources

    def _select_api_resource(self, api_resources: Dict[str, Dict]) -> Tuple[str, Dict]:
        """
        Select which API resource to generate OpenAPI for

        Parameters
        ----------
        api_resources : dict
            Dictionary of API resources

        Returns
        -------
        tuple
            (logical_id, resource_dict)

        Raises
        ------
        ApiResourceNotFoundException
            If specified API not found
        MultipleApiResourcesException
            If multiple APIs found and none specified
        """
        if self.api_logical_id:
            # User specified an API logical ID
            if self.api_logical_id not in api_resources:
                available_apis = ", ".join(api_resources.keys())
                raise ApiResourceNotFoundException(
                    self.api_logical_id, f"Available APIs: {available_apis}" if available_apis else "No APIs found"
                )
            return self.api_logical_id, api_resources[self.api_logical_id]

        # No API specified - check if there's only one
        if len(api_resources) == 1:
            logical_id = list(api_resources.keys())[0]
            return logical_id, api_resources[logical_id]

        # Multiple APIs and none specified
        raise MultipleApiResourcesException(list(api_resources.keys()))

    def _extract_existing_definition(self, resource: Dict, logical_id: str) -> Optional[Dict]:
        """
        Extract OpenAPI if already defined in DefinitionBody or DefinitionUri

        Parameters
        ----------
        resource : dict
            API resource dictionary
        logical_id : str
            Logical ID of the resource

        Returns
        -------
        dict or None
            OpenAPI document if found, None otherwise
        """
        properties = resource.get("Properties", {})
        definition_body = properties.get("DefinitionBody")
        definition_uri = properties.get("DefinitionUri")

        # For ApiGateway resources, check Body and BodyS3Location
        if not definition_body:
            definition_body = properties.get("Body")
        if not definition_uri:
            definition_uri = properties.get("BodyS3Location")

        if not definition_body and not definition_uri:
            LOG.debug("No DefinitionBody or DefinitionUri found in resource %s", logical_id)
            return None

        try:
            # Use SwaggerReader to handle various definition sources
            reader = SwaggerReader(definition_body=definition_body, definition_uri=definition_uri, working_dir=".")
            openapi_doc = reader.read()

            if openapi_doc:
                LOG.debug("Successfully extracted existing OpenAPI definition from resource %s", logical_id)
                return cast(Dict, openapi_doc)

        except Exception as e:
            LOG.debug("Failed to read existing definition: %s", str(e))

        return None

    def _generate_from_transformation(self, template: Dict, logical_id: str, resource: Dict) -> Dict:
        """
        Generate OpenAPI by transforming SAM template to CloudFormation

        Parameters
        ----------
        template : dict
            SAM template
        logical_id : str
            API logical ID
        resource : dict
            API resource

        Returns
        -------
        dict
            Generated OpenAPI document

        Raises
        ------
        TemplateTransformationException
            If transformation fails
        OpenApiExtractionException
            If OpenAPI extraction from transformed template fails
        """
        try:
            # Transform template using SAM Translator
            validator = SamTemplateValidator(
                sam_template=template,
                managed_policy_loader=None,
                profile=self.profile,
                region=self.region,
                parameter_overrides=self.parameter_overrides,
            )

            # Get transformed CloudFormation template
            transformed_str = validator.get_translated_template_if_valid()

            # Parse transformed template
            transformed_template = yaml_parse(transformed_str)

            # Extract OpenAPI from transformed resource
            openapi_doc = self._extract_from_cfn_template(transformed_template, logical_id, resource)

            return openapi_doc

        except InvalidSamDocumentException as e:
            raise TemplateTransformationException(str(e)) from e
        except Exception as e:
            raise TemplateTransformationException(f"Unexpected error during transformation: {str(e)}") from e

    def _extract_from_cfn_template(self, cfn_template: Dict, original_logical_id: str, original_resource: Dict) -> Dict:
        """
        Extract OpenAPI definition from transformed CloudFormation template

        Parameters
        ----------
        cfn_template : dict
            Transformed CloudFormation template
        original_logical_id : str
            Original SAM resource logical ID
        original_resource : dict
            Original SAM resource

        Returns
        -------
        dict
            OpenAPI document

        Raises
        ------
        OpenApiExtractionException
            If OpenAPI cannot be extracted
        """
        resources = cfn_template.get("Resources", {})

        # The transformed resource might have the same or different logical ID
        # For ServerlessRestApi created implicitly, SAM generates it with that name
        possible_ids = [original_logical_id, "ServerlessRestApi", "ServerlessHttpApi"]

        for resource_id in possible_ids:
            if resource_id in resources:
                resource = resources[resource_id]
                resource_type = resource.get("Type")

                # Check if it's an API Gateway resource
                if resource_type in [API_GATEWAY_REST_API, API_GATEWAY_V2_API]:
                    properties = resource.get("Properties", {})
                    definition_body = properties.get("Body") or properties.get("DefinitionBody")

                    if definition_body and isinstance(definition_body, dict):
                        LOG.debug("Extracted OpenAPI from transformed resource %s", resource_id)
                        return cast(Dict, definition_body)

        # If we couldn't find it in transformed resources, try the original approach
        raise OpenApiExtractionException(
            f"Could not extract OpenAPI definition from transformed template for resource '{original_logical_id}'. "
            "The resource may not generate an OpenAPI document or transformation failed."
        )

    def _validate_openapi(self, openapi_doc: Dict) -> bool:
        """
        Validate OpenAPI document structure

        Parameters
        ----------
        openapi_doc : dict
            OpenAPI document

        Returns
        -------
        bool
            True if valid, False otherwise
        """
        if not openapi_doc or not isinstance(openapi_doc, dict):
            return False

        # Check for required OpenAPI fields
        has_swagger = "swagger" in openapi_doc
        has_openapi = "openapi" in openapi_doc
        has_paths = "paths" in openapi_doc

        if not (has_swagger or has_openapi):
            LOG.warning("OpenAPI document missing 'swagger' or 'openapi' version field")
            return False

        if not has_paths:
            LOG.warning("OpenAPI document missing 'paths' field")
            return False

        return True

    def _has_implicit_api(self, template: Dict) -> bool:
        """
        Check if template has implicit API (functions with API events)

        Parameters
        ----------
        template : dict
            SAM template

        Returns
        -------
        bool
            True if template has functions with API events
        """
        resources = template.get("Resources", {})

        for resource in resources.values():
            if resource.get("Type") == "AWS::Serverless::Function":
                events = resource.get("Properties", {}).get("Events", {})
                for event in events.values():
                    event_type = event.get("Type", "")
                    if event_type in ["Api", "HttpApi"]:
                        return True

        return False

    def _generate_implicit_api(self, template: Dict, api_id: str) -> Dict:
        """
        Generate OpenAPI for implicit API by transforming template

        Parameters
        ----------
        template : dict
            SAM template
        api_id : str
            API logical ID (e.g., ServerlessRestApi)

        Returns
        -------
        dict
            Generated OpenAPI document

        Raises
        ------
        TemplateTransformationException
            If transformation fails
        OpenApiExtractionException
            If OpenAPI extraction fails
        """
        try:
            # Transform template using SAM Translator
            validator = SamTemplateValidator(
                sam_template=template,
                managed_policy_loader=None,
                profile=self.profile,
                region=self.region,
                parameter_overrides=self.parameter_overrides,
            )

            # Get transformed CloudFormation template
            transformed_str = validator.get_translated_template_if_valid()

            # Parse transformed template
            transformed_template = yaml_parse(transformed_str)

            # Extract OpenAPI from transformed implicit API
            resources = transformed_template.get("Resources", {})

            if api_id in resources:
                resource = resources[api_id]
                resource_type = resource.get("Type")

                if resource_type in [API_GATEWAY_REST_API, API_GATEWAY_V2_API]:
                    properties = resource.get("Properties", {})
                    definition_body = properties.get("Body") or properties.get("DefinitionBody")

                    if definition_body and isinstance(definition_body, dict):
                        LOG.debug("Extracted OpenAPI from implicit API %s", api_id)
                        return cast(Dict, definition_body)

            raise OpenApiExtractionException(
                f"Could not extract OpenAPI definition for implicit API '{api_id}'. "
                "The template may not generate an implicit API or transformation failed."
            )

        except InvalidSamDocumentException as e:
            raise TemplateTransformationException(str(e)) from e
        except OpenApiExtractionException:
            raise
        except Exception as e:
            raise TemplateTransformationException(f"Unexpected error during transformation: {str(e)}") from e

    def get_api_resources_info(self) -> List[Dict[str, str]]:
        """
        Get information about API resources in the template (useful for CLI output)

        Returns
        -------
        list
            List of dicts with API resource information
        """
        try:
            template = self._load_template()
            api_resources = self._find_api_resources(template)

            return [
                {"LogicalId": logical_id, "Type": resource.get("Type", "Unknown")}
                for logical_id, resource in api_resources.items()
            ]
        except Exception:
            return []
