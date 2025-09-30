"""
Local Lambda Function URL Service implementation
"""

import base64
import io
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Union

from flask import Response, jsonify, request

from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.services.base_local_service import BaseLocalService

LOG = logging.getLogger(__name__)


class FunctionUrlPayloadFormatter:
    """Formats HTTP requests to Lambda Function URL v2.0 format"""

    @staticmethod
    def _format_lambda_request(
        method: str,
        path: str,
        headers: Dict[str, str],
        query_params: Dict[str, str],
        body: Optional[str],
        source_ip: str,
        user_agent: str,
        host: str,
        port: int,
    ) -> Dict[str, Any]:
        """
        Format HTTP request to Lambda Function URL v2.0 payload

        Reference: https://docs.aws.amazon.com/lambda/latest/dg/urls-invocation.html
        """
        # Build raw query string
        raw_query_string = "&".join(f"{k}={v}" for k, v in query_params.items()) if query_params else ""

        # Determine if body is base64 encoded
        is_base64 = False
        if body:
            try:
                body.encode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                try:
                    body = base64.b64encode(body.encode("utf-8")).decode()
                    is_base64 = True
                except Exception:
                    pass

        # Extract cookies from headers
        cookies = []
        cookie_header = headers.get("Cookie", "")
        if cookie_header:
            cookies = cookie_header.split("; ")

        return {
            "version": "2.0",
            "routeKey": "$default",
            "rawPath": path,
            "rawQueryString": raw_query_string,
            "cookies": cookies,
            "headers": dict(headers),
            "queryStringParameters": query_params if query_params else None,
            "requestContext": {
                "accountId": "123456789012",  # Mock account ID for local testing
                "apiId": f"function-url-{uuid.uuid4().hex[:8]}",
                "domainName": f"{host}:{port}",
                "domainPrefix": "function-url-local",
                "http": {
                    "method": method,
                    "path": path,
                    "protocol": "HTTP/1.1",
                    "sourceIp": source_ip,
                    "userAgent": user_agent,
                },
                "requestId": str(uuid.uuid4()),
                "routeKey": "$default",
                "stage": "$default",
                "time": datetime.now(timezone.utc).strftime("%d/%b/%Y:%H:%M:%S +0000"),
                "timeEpoch": int(time.time() * 1000),
            },
            "body": body,
            "pathParameters": None,
            "isBase64Encoded": is_base64,
            "stageVariables": None,
        }

    @staticmethod
    def _parse_lambda_response(lambda_response: Union[Dict[str, Any], str]) -> Tuple[int, Dict, str]:
        """
        Parse Lambda response and format for HTTP response

        Returns: (status_code, headers, body)
        """
        # Handle string responses (just the body)
        if isinstance(lambda_response, str):
            return 200, {}, lambda_response

        # Handle dict responses - at this point we know it's a dict
        status_code = lambda_response.get("statusCode", 200)
        headers = lambda_response.get("headers", {})
        body = lambda_response.get("body", "")

        # Handle base64 encoded responses
        if lambda_response.get("isBase64Encoded", False) and body:
            try:
                body = base64.b64decode(body)
            except Exception as e:
                LOG.warning(f"Failed to decode base64 body: {e}")

        # Handle multi-value headers
        multi_headers = lambda_response.get("multiValueHeaders", {})
        for key, values in multi_headers.items():
            if isinstance(values, list):
                headers[key] = ", ".join(str(v) for v in values)

        # Add cookies to headers
        cookies = lambda_response.get("cookies", [])
        if cookies:
            headers["Set-Cookie"] = "; ".join(cookies)

        return status_code, headers, body


class FunctionUrlHandler(BaseLocalService):
    """Individual Lambda Function URL handler"""

    def __init__(
        self,
        function_name: str,
        function_config: Dict,
        local_lambda_runner,
        port: int,  # local_lambda_runner is actually LocalLambdaRunner
        host: str = "127.0.0.1",
        disable_authorizer: bool = False,
        stderr: Optional[StreamWriter] = None,
        is_debugging: bool = False,
        ssl_context=None,
    ):
        """
        Initialize the Function URL service

        Parameters
        ----------
        function_name : str
            Name of the Lambda function
        function_config : Dict
            Function URL configuration from template
        local_lambda_runner : LocalLambdaRunner
            Lambda runner to execute functions (has provider and local_runtime)
        port : int
            Port to run the service on
        host : str
            Host to bind to
        disable_authorizer : bool
            Whether to disable authorization checks
        stderr : Optional[StreamWriter]
            Stream writer for error output
        is_debugging : bool
            Whether debugging is enabled
        ssl_context : Optional[Tuple[str, str]]
            Optional SSL context for HTTPS
        """
        super().__init__(is_debugging=is_debugging, port=port, host=host, ssl_context=ssl_context)
        self.function_name = function_name
        self.function_config = function_config
        self.local_lambda_runner = local_lambda_runner
        self.disable_authorizer = disable_authorizer
        self.stderr = stderr or StreamWriter(sys.stderr)

    def create(self):
        """
        Create the Flask application with routes configured.
        This is called by the base class before starting the service.
        """
        from flask import Flask
        
        self._app = Flask(__name__)
        self._configure_routes()
        return self._app

    def _configure_routes(self):
        """Configure Flask routes for Function URL"""

        @self._app.route(
            "/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        )
        @self._app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
        def handle_request(path):
            """Handle all HTTP requests to Function URL"""

            # Build the full path
            full_path = f"/{path}" if path else "/"

            # Handle CORS preflight requests
            if request.method == "OPTIONS":
                return self._handle_cors_preflight()

            # Format request to v2.0 payload
            event = FunctionUrlPayloadFormatter._format_lambda_request(
                method=request.method,
                path=full_path,
                headers=dict(request.headers),
                query_params=request.args.to_dict(),
                body=request.get_data(as_text=True) if request.data else None,
                source_ip=request.remote_addr or "127.0.0.1",
                user_agent=request.user_agent.string if request.user_agent else "",
                host=self.host,
                port=self.port,
            )

            # Check authorization if enabled
            auth_type = self.function_config.get("auth_type", "AWS_IAM")
            if auth_type == "AWS_IAM" and not self.disable_authorizer:
                if not self._validate_iam_auth(request):
                    return Response("Forbidden", status=403)

            # Invoke Lambda function
            try:
                LOG.debug(f"Invoking function {self.function_name} with event: {json.dumps(event)[:500]}...")

                # Get the function from the provider
                function = self.local_lambda_runner.provider.get(self.function_name)
                if not function:
                    LOG.error(f"Function {self.function_name} not found")
                    return Response("Function not found", status=404)

                # Get the invoke configuration
                config = self.local_lambda_runner.get_invoke_config(function)

                # Create stream writers for stdout and stderr
                stdout_stream = io.StringIO()
                stderr_stream = io.StringIO()
                stdout_writer = StreamWriter(stdout_stream)
                stderr_writer = StreamWriter(stderr_stream)

                # Invoke the function using the runtime directly
                # The config already contains the proper environment variables from get_invoke_config
                self.local_lambda_runner.local_runtime.invoke(
                    config,
                    json.dumps(event),
                    debug_context=self.local_lambda_runner.debug_context,
                    stdout=stdout_writer,
                    stderr=stderr_writer,
                    container_host=self.local_lambda_runner.container_host,
                    container_host_interface=self.local_lambda_runner.container_host_interface,
                    extra_hosts=self.local_lambda_runner.extra_hosts,
                )

                # Get the output
                stdout = stdout_stream.getvalue()
                stderr = stderr_stream.getvalue()

                # Check for Lambda runtime errors in stderr
                if stderr and ("errorMessage" in stderr or "errorType" in stderr):
                    LOG.error(f"Lambda function {self.function_name} failed with error: {stderr}")
                    return Response(
                        json.dumps({"message": "Internal server error", "type": "LambdaFunctionError"}),
                        status=502,
                        headers={"Content-Type": "application/json"},
                    )

                # Parse Lambda response
                try:
                    lambda_response = json.loads(stdout) if stdout else {}
                except json.JSONDecodeError as e:
                    LOG.warning(f"Failed to parse Lambda response as JSON: {e}. Returning 502.")
                    return Response(
                        json.dumps({"message": "The Lambda function returned an invalid response"}),
                        status=502,
                        headers={"Content-Type": "application/json"},
                    )

                # Format response
                status_code, headers, body = FunctionUrlPayloadFormatter._parse_lambda_response(lambda_response)

                # Add CORS headers if configured
                cors_headers = self._get_cors_headers()
                headers.update(cors_headers)

                return Response(body, status=status_code, headers=headers)

            except Exception as e:
                LOG.error(f"Error invoking function {self.function_name}: {e}", exc_info=True)
                # Return 502 Bad Gateway for Lambda invocation errors
                return Response(
                    json.dumps({"message": "Bad Gateway", "error": str(e)}),
                    status=502,
                    headers={"Content-Type": "application/json"},
                )

        @self._app.errorhandler(404)
        def not_found(e):
            """Handle 404 errors"""
            return jsonify({"message": "Not found"}), 404

        @self._app.errorhandler(500)
        def internal_error(e):
            """Handle 500 errors"""
            LOG.error(f"Internal server error: {e}")
            return jsonify({"message": "Internal server error"}), 500

    def _handle_cors_preflight(self):
        """Handle CORS preflight requests"""
        cors_config = self.function_config.get("cors", {})

        headers = {}

        # Add CORS headers based on configuration
        if cors_config:
            origins = cors_config.get("AllowOrigins", ["*"])
            methods = cors_config.get("AllowMethods", ["*"])
            allow_headers = cors_config.get("AllowHeaders", ["*"])
            max_age = cors_config.get("MaxAge", 86400)

            headers["Access-Control-Allow-Origin"] = ", ".join(origins)
            headers["Access-Control-Allow-Methods"] = ", ".join(methods)
            headers["Access-Control-Allow-Headers"] = ", ".join(allow_headers)
            headers["Access-Control-Max-Age"] = str(max_age)
        else:
            # Default permissive CORS for local development
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "*"
            headers["Access-Control-Max-Age"] = "86400"

        return Response("", status=200, headers=headers)

    def _get_cors_headers(self):
        """Get CORS headers based on configuration"""
        cors_config = self.function_config.get("cors", {})

        if not cors_config:
            return {}

        headers = {}

        origins = cors_config.get("AllowOrigins", ["*"])
        headers["Access-Control-Allow-Origin"] = ", ".join(origins)

        if cors_config.get("AllowCredentials"):
            headers["Access-Control-Allow-Credentials"] = "true"

        expose_headers = cors_config.get("ExposeHeaders")
        if expose_headers:
            headers["Access-Control-Expose-Headers"] = ", ".join(expose_headers)

        return headers

    def _validate_iam_auth(self, request) -> bool:
        """
        Validate IAM authorization (simplified for local testing)

        In production, this would validate AWS SigV4 signatures.
        For local development, we just check for the presence of an Authorization header.

        WARNING: This is a mock implementation for local testing only.
        Real IAM authorization with signature validation is not performed.
        """
        if self.disable_authorizer:
            return True

        # Simple check for Authorization header presence
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            LOG.debug("No Authorization header found")
            return False

        # In local mode, accept any Authorization header that starts with "AWS4-HMAC-SHA256"
        if auth_header.startswith("AWS4-HMAC-SHA256"):
            LOG.warning(
                "IAM authorization is simplified for local testing. "
                "Any AWS4-HMAC-SHA256 header is accepted. "
                "Use --disable-authorizer flag to skip authorization checks entirely."
            )
            return True

        LOG.debug(f"Invalid Authorization header format: {auth_header[:20]}...")
        return False

    def start(self):
        """Start the Function URL service in a background thread"""
        LOG.info(f"Starting Function URL for {self.function_name} at http://{self.host}:{self.port}/")
        
        # Create the Flask app if not already created
        if not self._app:
            self.create()
        
        # Start Flask in a separate thread since run() is blocking
        from threading import Thread
        self._server_thread = Thread(target=self.run, daemon=True)
        self._server_thread.start()
        
        # Give Flask a moment to start
        time.sleep(0.5)

    def stop(self):
        """Stop the Function URL service"""
        LOG.info(f"Stopping Function URL service for {self.function_name}")
        # Flask doesn't have a built-in way to stop cleanly
        # The service will be stopped when the process terminates
        pass
