"""
Convert Swagger 2.0 to OpenAPI 3.0 specification
"""

import copy
from typing import Dict


class OpenApiConverter:
    """Converts Swagger 2.0 specs to OpenAPI 3.0"""

    @staticmethod
    def swagger_to_openapi3(swagger_doc: Dict) -> Dict:
        """
        Convert Swagger 2.0 document to OpenAPI 3.0

        Parameters
        ----------
        swagger_doc : dict
            Swagger 2.0 document

        Returns
        -------
        dict
            OpenAPI 3.0 document
        """
        if not swagger_doc or not isinstance(swagger_doc, dict):
            return swagger_doc

        # Check if already OpenAPI 3.0
        if "openapi" in swagger_doc:
            return swagger_doc

        # Check if Swagger 2.0
        if "swagger" not in swagger_doc:
            return swagger_doc

        # Create OpenAPI 3.0 document
        openapi_doc = copy.deepcopy(swagger_doc)

        # 1. Change version
        openapi_doc["openapi"] = "3.0.0"
        del openapi_doc["swagger"]

        # 2. Move securityDefinitions to components.securitySchemes
        if "securityDefinitions" in openapi_doc:
            if "components" not in openapi_doc:
                openapi_doc["components"] = {}
            openapi_doc["components"]["securitySchemes"] = openapi_doc["securityDefinitions"]
            del openapi_doc["securityDefinitions"]

        # 3. Keep x-amazon-apigateway extensions as is (API Gateway specific)
        # These are AWS extensions that work in both formats

        return openapi_doc
