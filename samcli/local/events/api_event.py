"""Holds Classes for API Gateway to Lambda Events"""
from time import time
from datetime import datetime
import uuid


class ContextIdentity:
    def __init__(
        self,
        api_key=None,
        user_arn=None,
        cognito_authentication_type=None,
        caller=None,
        user_agent="Custom User Agent String",
        user=None,
        cognito_identity_pool_id=None,
        cognito_authentication_provider=None,
        source_ip="127.0.0.1",
        account_id=None,
    ):
        """
        Constructs a ContextIdentity

        :param str api_key: API Key used for the request
        :param str user_arn: ARN of the caller
        :param str cognito_authentication_type: Auth Type used
        :param str caller: Caller that make the request
        :param str user_agent: User agent (Default: Custom User Agent String)
        :param str user: User
        :param str cognito_identity_pool_id: Identity Pool Id used
        :param str cognito_authentication_provider: Auth Provider
        :param str source_ip: Source Ip of the request (Default: 127.0.0.1)
        :param str account_id: Account Id of the request
        """
        self.api_key = api_key
        self.user_arn = user_arn
        self.cognito_authentication_type = cognito_authentication_type
        self.caller = caller
        self.user_agent = user_agent
        self.user = user
        self.cognito_identity_pool_id = cognito_identity_pool_id
        self.cognito_authentication_provider = cognito_authentication_provider
        self.source_ip = source_ip
        self.account_id = account_id

    def to_dict(self):
        """
        Constructs an dictionary representation of the Identity Object to be used in serializing to JSON

        :return: dict representing the object
        """
        json_dict = {
            "apiKey": self.api_key,
            "userArn": self.user_arn,
            "cognitoAuthenticationType": self.cognito_authentication_type,
            "caller": self.caller,
            "userAgent": self.user_agent,
            "user": self.user,
            "cognitoIdentityPoolId": self.cognito_identity_pool_id,
            "cognitoAuthenticationProvider": self.cognito_authentication_provider,
            "sourceIp": self.source_ip,
            "accountId": self.account_id,
        }

        return json_dict


class RequestContext:
    def __init__(
        self,
        resource_id="123456",
        api_id="1234567890",
        resource_path=None,
        http_method=None,
        request_id=str(uuid.uuid4()),
        account_id="123456789012",
        stage=None,
        identity=None,
        extended_request_id=None,
        path=None,
        protocol=None,
        domain_name=None,
        request_time_epoch=int(time()),
        request_time=datetime.utcnow().strftime("%d/%b/%Y:%H:%M:%S +0000"),
    ):
        """
        Constructs a RequestContext

        :param str resource_id: Resource Id of the Request (Default: 123456)
        :param str api_id: Api Id for the Request (Default: 1234567890)
        :param str resource_path: Path for the Request
        :param str http_method: HTTPMethod for the request
        :param str request_id: Request Id for the request (Default: generated uuid id)
        :param str account_id: Account Id of the Request (Default: 123456789012)
        :param str stage: Api Gateway Stage
        :param ContextIdentity identity: Identity for the Request
        :param str extended_request_id:
        :param str path:
        """

        self.resource_id = resource_id
        self.api_id = api_id
        self.resource_path = resource_path
        self.http_method = http_method
        self.request_id = request_id
        self.account_id = account_id
        self.stage = stage
        self.identity = identity
        self.extended_request_id = extended_request_id
        self.path = path
        self.protocol = protocol
        self.domain_name = domain_name
        self.request_time_epoch = request_time_epoch
        self.request_time = request_time

    def to_dict(self):
        """
        Constructs an dictionary representation of the RequestContext Object to be used in serializing to JSON

        :return: dict representing the object
        """
        identity_dict = {}
        if self.identity:
            identity_dict = self.identity.to_dict()

        json_dict = {
            "resourceId": self.resource_id,
            "apiId": self.api_id,
            "resourcePath": self.resource_path,
            "httpMethod": self.http_method,
            "requestId": self.request_id,
            "accountId": self.account_id,
            "stage": self.stage,
            "identity": identity_dict,
            "extendedRequestId": self.extended_request_id,
            "path": self.path,
            "protocol": self.protocol,
            "domainName": self.domain_name,
            "requestTimeEpoch": self.request_time_epoch,
            "requestTime": self.request_time,
        }

        return json_dict


class ApiGatewayLambdaEvent:
    def __init__(
        self,
        http_method=None,
        body=None,
        resource=None,
        request_context=None,
        query_string_params=None,
        multi_value_query_string_params=None,
        headers=None,
        multi_value_headers=None,
        path_parameters=None,
        stage_variables=None,
        path=None,
        is_base_64_encoded=False,
    ):
        """
        Constructs an ApiGatewayLambdaEvent

        :param str http_method: HTTPMethod of the request
        :param str body: Body or data for the request
        :param str resource: Resource for the reqeust
        :param RequestContext request_context: RequestContext for the request
        :param dict query_string_params: Query String parameters
        :param dict multi_value_query_string_params: Multi-value Query String parameters
        :param dict headers: dict of the request Headers
        :param dict multi_value_headers: dict of the multi-value request Headers
        :param dict path_parameters: Path Parameters
        :param dict stage_variables: API Gateway Stage Variables
        :param str path: Path of the request
        :param bool is_base_64_encoded: True if the data is base64 encoded.
        """

        if not isinstance(query_string_params, dict) and query_string_params is not None:
            raise TypeError("'query_string_params' must be of type dict or None")

        if not isinstance(multi_value_query_string_params, dict) and multi_value_query_string_params is not None:
            raise TypeError("'multi_value_query_string_params' must be of type dict or None")

        if not isinstance(headers, dict) and headers is not None:
            raise TypeError("'headers' must be of type dict or None")

        if not isinstance(multi_value_headers, dict) and multi_value_headers is not None:
            raise TypeError("'multi_value_headers' must be of type dict or None")

        if not isinstance(path_parameters, dict) and path_parameters is not None:
            raise TypeError("'path_parameters' must be of type dict or None")

        if not isinstance(stage_variables, dict) and stage_variables is not None:
            raise TypeError("'stage_variables' must be of type dict or None")

        self.version = "1.0"
        self.http_method = http_method
        self.body = body
        self.resource = resource
        self.request_context = request_context
        self.query_string_params = query_string_params
        self.multi_value_query_string_params = multi_value_query_string_params
        self.headers = headers
        self.multi_value_headers = multi_value_headers
        self.path_parameters = path_parameters
        self.stage_variables = stage_variables
        self.path = path
        self.is_base_64_encoded = is_base_64_encoded

    def to_dict(self):
        """
        Constructs an dictionary representation of the ApiGatewayLambdaEvent Object to be used in serializing to JSON

        :return: dict representing the object
        """
        request_context_dict = {}
        if self.request_context:
            request_context_dict = self.request_context.to_dict()

        json_dict = {
            "version": self.version,
            "httpMethod": self.http_method,
            "body": self.body if self.body else None,
            "resource": self.resource,
            "requestContext": request_context_dict,
            "queryStringParameters": dict(self.query_string_params) if self.query_string_params else None,
            "multiValueQueryStringParameters": dict(self.multi_value_query_string_params)
            if self.multi_value_query_string_params
            else None,
            "headers": dict(self.headers) if self.headers else None,
            "multiValueHeaders": dict(self.multi_value_headers) if self.multi_value_headers else None,
            "pathParameters": dict(self.path_parameters) if self.path_parameters else None,
            "stageVariables": dict(self.stage_variables) if self.stage_variables else None,
            "path": self.path,
            "isBase64Encoded": self.is_base_64_encoded,
        }

        return json_dict


class ContextHTTP:
    def __init__(
        self, method=None, path=None, protocol="HTTP/1.1", source_ip="127.0.0.1", user_agent="Custom User Agent String"
    ):
        """
        Constructs a ContextHTTP

        :param str method: HTTP Method for the request
        :param str path: HTTP Path for the request
        :param str protocol: HTTP Protocol for the request (Default: HTTP/1.1)
        :param str source_ip: Source IP for the request (Default: 127.0.0.1)
        :param str user_agent: User agent (Default: Custom User Agent String)
        """
        self.method = method
        self.path = path
        self.protocol = protocol
        self.source_ip = source_ip
        self.user_agent = user_agent

    def to_dict(self):
        """
        Constructs an dictionary representation of the HTTP Object to be used
        in serializing to JSON

        :return: dict representing the object
        """
        json_dict = {
            "method": self.method,
            "path": self.path,
            "protocol": self.protocol,
            "sourceIp": self.source_ip,
            "userAgent": self.user_agent,
        }

        return json_dict


class RequestContextV2:
    def __init__(
        self,
        account_id="123456789012",
        api_id="1234567890",
        http=None,
        request_id=str(uuid.uuid4()),
        route_key=None,
        stage=None,
    ):
        """
        Constructs a RequestContext Version 2.

        :param str account_id: Account Id of the Request (Default: 123456789012)
        :param str api_id: Api Id for the Request (Default: 1234567890)
        :param ContextHTTP http: HTTP for the request
        :param str request_id: Request Id for the request (Default: generated uuid id)
        :param str route_key: The route key for the route.
        :param str stage: Api Gateway V2 Stage
        """

        self.account_id = account_id
        self.api_id = api_id
        self.http = http
        self.request_id = request_id
        self.route_key = route_key
        self.stage = stage

    def to_dict(self):
        """
        Constructs an dictionary representation of the RequestContext Version 2
        Object to be used in serializing to JSON

        :return: dict representing the object
        """
        http_dict = {}
        if self.http:
            http_dict = self.http.to_dict()

        json_dict = {
            "accountId": self.account_id,
            "apiId": self.api_id,
            "http": http_dict,
            "requestId": self.request_id,
            "routeKey": self.route_key,
            "stage": self.stage,
        }

        return json_dict


class ApiGatewayV2LambdaEvent:
    def __init__(
        self,
        route_key=None,
        raw_path=None,
        raw_query_string=None,
        cookies=None,
        headers=None,
        query_string_params=None,
        request_context=None,
        body=None,
        path_parameters=None,
        stage_variables=None,
        is_base_64_encoded=False,
    ):
        """
        Constructs an ApiGatewayV2LambdaEvent.

        :param str route_key: The route key for the route.
        :param str raw_path: The raw path of the request.
        :param str raw_query_string: The raw query string of the request.
        :param list cookies: All cookie headers in the request are combined with commas and added to this field.
        :param dict headers: dict of the request Headers. Duplicate headers are combined with commas.
        :param dict query_string_params: Query String parameters.
        :param RequestContextV2 request_context: RequestContextV2 for the request
        :param str body: Body or data for the request
        :param dict path_parameters: Path Parameters
        :param dict stage_variables: API Gateway Stage Variables
        :param bool is_base_64_encoded: True if the data is base64 encoded.
        """

        if not isinstance(cookies, list) and cookies is not None:
            raise TypeError("'cookies' must be of type list or None")

        if not isinstance(headers, dict) and headers is not None:
            raise TypeError("'headers' must be of type dict or None")

        if not isinstance(query_string_params, dict) and query_string_params is not None:
            raise TypeError("'query_string_params' must be of type dict or None")

        if not isinstance(path_parameters, dict) and path_parameters is not None:
            raise TypeError("'path_parameters' must be of type dict or None")

        if not isinstance(stage_variables, dict) and stage_variables is not None:
            raise TypeError("'stage_variables' must be of type dict or None")

        self.version = "2.0"
        self.route_key = route_key
        self.raw_path = raw_path
        self.raw_query_string = raw_query_string
        self.cookies = cookies
        self.headers = headers
        self.query_string_params = query_string_params
        self.request_context = request_context
        self.body = body
        self.path_parameters = path_parameters
        self.is_base_64_encoded = is_base_64_encoded
        self.stage_variables = stage_variables

    def to_dict(self):
        """
        Constructs an dictionary representation of the ApiGatewayLambdaEvent
        Version 2 Object to be used in serializing to JSON

        :return: dict representing the object
        """
        request_context_dict = {}
        if self.request_context:
            request_context_dict = self.request_context.to_dict()

        json_dict = {
            "version": self.version,
            "routeKey": self.route_key,
            "rawPath": self.raw_path,
            "rawQueryString": self.raw_query_string,
            "cookies": self.cookies,
            "headers": self.headers,
            "queryStringParameters": self.query_string_params,
            "requestContext": request_context_dict,
            "body": self.body,
            "pathParameters": self.path_parameters,
            "stageVariables": self.stage_variables,
            "isBase64Encoded": self.is_base_64_encoded,
        }

        return json_dict
