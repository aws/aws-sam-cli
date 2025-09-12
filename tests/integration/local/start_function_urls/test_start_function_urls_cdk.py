"""
Integration tests for sam local start-function-urls command with CDK templates
"""

import json
import os
import tempfile
from unittest import TestCase, skipIf

import requests
from parameterized import parameterized

from tests.integration.local.start_function_urls.start_function_urls_integ_base import (
    StartFunctionUrlsIntegBaseClass,
    WritableStartFunctionUrlsIntegBaseClass
)
from tests.testing_utils import (
    RUNNING_ON_CI,
    RUNNING_TEST_FOR_MASTER_ON_CI,
    RUN_BY_CANARY,
)


@skipIf(
    (RUNNING_ON_CI and not RUN_BY_CANARY) and not RUNNING_TEST_FOR_MASTER_ON_CI,
    "Skip integration tests on CI unless running canary or master",
)
class TestStartFunctionUrlsCDK(WritableStartFunctionUrlsIntegBaseClass):
    """
    Integration tests for start-function-urls with CDK templates
    """

    template_content = """
    {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Transform": "AWS::Serverless-2016-10-31",
        "Resources": {
            "CDKFunction": {
                "Type": "AWS::Serverless::Function",
                "Properties": {
                    "CodeUri": ".",
                    "Handler": "main.handler",
                    "Runtime": "python3.9",
                    "FunctionUrlConfig": {
                        "AuthType": "NONE"
                    }
                }
            }
        }
    }
    """

    code_content = """
import json

def handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Hello from CDK Function URL!',
            'source': 'cdk'
        })
    }
"""

    def test_cdk_function_url_basic(self):
        """Test basic Function URL with CDK-generated template"""
        # Start service
        self.assertTrue(
            self.start_function_urls(self.template),
            "Failed to start Function URLs service with CDK template"
        )
        
        # Test GET request
        response = requests.get(f"{self.url}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Hello from CDK Function URL!")
        self.assertEqual(data["source"], "cdk")

    def test_cdk_function_url_with_cors(self):
        """Test Function URL with CORS configuration in CDK template"""
        # Create CDK template with CORS
        cdk_cors_template = """
        {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "CDKCorsFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": ".",
                        "Handler": "main.handler",
                        "Runtime": "python3.9",
                        "FunctionUrlConfig": {
                            "AuthType": "NONE",
                            "Cors": {
                                "AllowOrigins": ["https://example.com"],
                                "AllowMethods": ["GET", "POST"],
                                "AllowHeaders": ["Content-Type", "X-Custom-Header"],
                                "MaxAge": 300
                            }
                        }
                    }
                }
            }
        }
        """
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write CDK template
            template_path = os.path.join(temp_dir, "cdk-template.json")
            with open(template_path, "w") as f:
                f.write(cdk_cors_template)
            
            # Write function code
            with open(os.path.join(temp_dir, "main.py"), "w") as f:
                f.write(self.code_content)
            
            # Start service
            self.assertTrue(
                self.start_function_urls(template_path),
                "Failed to start Function URLs service with CDK CORS template"
            )
            
            # Test CORS preflight request
            response = requests.options(
                f"{self.url}/",
                headers={
                    "Origin": "https://example.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type"
                }
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("Access-Control-Allow-Origin", response.headers)

    @parameterized.expand([
        ("AWS_IAM",),
        ("NONE",),
    ])
    def test_cdk_function_url_auth_types(self, auth_type):
        """Test Function URL with different auth types in CDK template"""
        # Create CDK template with specific auth type
        cdk_auth_template = f"""
        {{
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {{
                "CDKAuthFunction": {{
                    "Type": "AWS::Serverless::Function",
                    "Properties": {{
                        "CodeUri": ".",
                        "Handler": "main.handler",
                        "Runtime": "python3.9",
                        "FunctionUrlConfig": {{
                            "AuthType": "{auth_type}"
                        }}
                    }}
                }}
            }}
        }}
        """
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write CDK template
            template_path = os.path.join(temp_dir, "cdk-auth-template.json")
            with open(template_path, "w") as f:
                f.write(cdk_auth_template)
            
            # Write function code
            with open(os.path.join(temp_dir, "main.py"), "w") as f:
                f.write(self.code_content)
            
            # Start service
            self.assertTrue(
                self.start_function_urls(template_path),
                f"Failed to start Function URLs service with CDK {auth_type} auth template"
            )
            
            # Test request
            response = requests.get(f"{self.url}/")
            
            if auth_type == "AWS_IAM":
                # Should require authentication
                self.assertEqual(response.status_code, 403)
            else:
                # Should allow without authentication
                self.assertEqual(response.status_code, 200)

    def test_cdk_multiple_function_urls(self):
        """Test multiple Function URLs in a single CDK template"""
        # Create CDK template with multiple functions
        cdk_multi_template = """
        {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "CDKFunction1": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": ".",
                        "Handler": "func1.handler",
                        "Runtime": "python3.9",
                        "FunctionUrlConfig": {
                            "AuthType": "NONE"
                        }
                    }
                },
                "CDKFunction2": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": ".",
                        "Handler": "func2.handler",
                        "Runtime": "python3.9",
                        "FunctionUrlConfig": {
                            "AuthType": "NONE"
                        }
                    }
                }
            }
        }
        """
        
        func1_content = """
import json

def handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'function': 'CDKFunction1'})
    }
"""
        
        func2_content = """
import json

def handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'function': 'CDKFunction2'})
    }
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write CDK template
            template_path = os.path.join(temp_dir, "cdk-multi-template.json")
            with open(template_path, "w") as f:
                f.write(cdk_multi_template)
            
            # Write function codes
            with open(os.path.join(temp_dir, "func1.py"), "w") as f:
                f.write(func1_content)
            with open(os.path.join(temp_dir, "func2.py"), "w") as f:
                f.write(func2_content)
            
            # Start service with port range
            base_port = int(self.port)
            self.assertTrue(
                self.start_function_urls(
                    template_path,
                    extra_args=f"--port-range {base_port}-{base_port+10}"
                ),
                "Failed to start Function URLs service with multiple CDK functions"
            )
            
            # Test that at least one function is accessible
            found_functions = []
            for port_offset in range(10):
                try:
                    response = requests.get(
                        f"http://{self.host}:{base_port + port_offset}/",
                        timeout=1
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if "function" in data:
                            found_functions.append(data["function"])
                except:
                    pass
            
            self.assertGreater(len(found_functions), 0, "No CDK functions were accessible")

    def test_cdk_function_url_with_environment_variables(self):
        """Test Function URL with environment variables in CDK template"""
        # Create CDK template with environment variables
        cdk_env_template = """
        {
            "AWSTemplateFormatVersion": "2010-09-09",
            "Transform": "AWS::Serverless-2016-10-31",
            "Resources": {
                "CDKEnvFunction": {
                    "Type": "AWS::Serverless::Function",
                    "Properties": {
                        "CodeUri": ".",
                        "Handler": "env.handler",
                        "Runtime": "python3.9",
                        "Environment": {
                            "Variables": {
                                "APP_NAME": "CDKApp",
                                "APP_VERSION": "2.0.0",
                                "DEPLOYMENT": "CDK"
                            }
                        },
                        "FunctionUrlConfig": {
                            "AuthType": "NONE"
                        }
                    }
                }
            }
        }
        """
        
        env_function_content = """
import json
import os

def handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({
            'app_name': os.environ.get('APP_NAME', 'Unknown'),
            'app_version': os.environ.get('APP_VERSION', 'Unknown'),
            'deployment': os.environ.get('DEPLOYMENT', 'Unknown')
        })
    }
"""
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Write CDK template
            template_path = os.path.join(temp_dir, "cdk-env-template.json")
            with open(template_path, "w") as f:
                f.write(cdk_env_template)
            
            # Write function code
            with open(os.path.join(temp_dir, "env.py"), "w") as f:
                f.write(env_function_content)
            
            # Start service
            self.assertTrue(
                self.start_function_urls(template_path),
                "Failed to start Function URLs service with CDK environment variables"
            )
            
            # Test environment variables
            response = requests.get(f"{self.url}/")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["app_name"], "CDKApp")
            self.assertEqual(data["app_version"], "2.0.0")
            self.assertEqual(data["deployment"], "CDK")


if __name__ == "__main__":
    import unittest
    unittest.main()
