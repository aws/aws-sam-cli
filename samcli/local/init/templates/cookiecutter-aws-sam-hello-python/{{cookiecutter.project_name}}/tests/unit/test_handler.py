from collections import namedtuple
import json

import pytest

from hello_world import app


@pytest.fixture()
def lambda_context():
    """ Generates a dummy Lamba context """

    context = namedtuple(
        "context",
        [
            "aws_request_id",
            "client_context",
            "function_name",
            "function_version",
            "identity",
            "invoked_function_arn",
            "log_group_name",
            "log_stream_name",
            "memory_limit_in_mb",
        ],
    )

    context.aws_request_id = "a1c0d36a-4371-457a-a8d4-8cda6958244e"
    context.client_context = None
    context.function_name = "test"
    context.function_version = "$LATEST"
    context.identity = None
    context.invoked_function_arn = "arn:aws:lambda:eu-west-1:738236477645:function:test"
    context.log_group_name = "/aws/lambda/test"
    context.log_stream_name = "2018/7/12/[$LATEST]5979abf592037c9f"
    context.memory_limit_in_mb = "128"

    return context


@pytest.fixture()
def apigw_event():
    """ Generates API GW Event"""

    return {
        "body": '{ "test": "body"}',
        "resource": "/{proxy+}",
        "requestContext": {
            "resourceId": "123456",
            "apiId": "1234567890",
            "resourcePath": "/{proxy+}",
            "httpMethod": "POST",
            "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
            "accountId": "123456789012",
            "identity": {
                "apiKey": "",
                "userArn": "",
                "cognitoAuthenticationType": "",
                "caller": "",
                "userAgent": "Custom User Agent String",
                "user": "",
                "cognitoIdentityPoolId": "",
                "cognitoIdentityId": "",
                "cognitoAuthenticationProvider": "",
                "sourceIp": "127.0.0.1",
                "accountId": "",
            },
            "stage": "prod",
        },
        "queryStringParameters": {"foo": "bar"},
        "headers": {
            "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
            "Accept-Language": "en-US,en;q=0.8",
            "CloudFront-Is-Desktop-Viewer": "true",
            "CloudFront-Is-SmartTV-Viewer": "false",
            "CloudFront-Is-Mobile-Viewer": "false",
            "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
            "CloudFront-Viewer-Country": "US",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "X-Forwarded-Port": "443",
            "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
            "X-Forwarded-Proto": "https",
            "X-Amz-Cf-Id": "aaaaaaaaaae3VYQb9jd-nvCd-de396Uhbp027Y2JvkCPNLmGJHqlaA==",
            "CloudFront-Is-Tablet-Viewer": "false",
            "Cache-Control": "max-age=0",
            "User-Agent": "Custom User Agent String",
            "CloudFront-Forwarded-Proto": "https",
            "Accept-Encoding": "gzip, deflate, sdch",
        },
        "pathParameters": {"proxy": "/examplepath"},
        "httpMethod": "POST",
        "stageVariables": {"baz": "qux"},
        "path": "/examplepath",
    }


def test_lambda_handler(apigw_event, mocker):

    requests_response_mock = namedtuple("response", ["text"])
    requests_response_mock.text = "1.1.1.1\n"

    request_mock = mocker.patch.object(
        app.requests, 'get', side_effect=requests_response_mock)

    ret = app.lambda_handler(apigw_event, "")
    assert ret["statusCode"] == 200

    for key in ("message", "location"):
        assert key in ret["body"]

    data = json.loads(ret["body"])
    assert data["message"] == "hello world"


def test_lambda_handler_error(apigw_event, lambda_context, mocker):

    mocker.patch.object(app.requests, 'get',
                        side_effect=app.requests.RequestException)
    ret = app.lambda_handler(apigw_event, lambda_context)

    assert ret["statusCode"] == 500

    for key in ("message", "request_id"):
        assert key in ret["body"]

    data = json.loads(ret["body"])
    assert data["message"] == "Something went wrong :("
