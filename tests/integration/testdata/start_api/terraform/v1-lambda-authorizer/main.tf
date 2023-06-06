provider "aws" {}

resource "aws_api_gateway_authorizer" "header_authorizer" {
  name = "header_authorizer"
  rest_api_id = aws_api_gateway_rest_api.api.id
  authorizer_uri = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.invocation_role.arn
  identity_source = "method.request.header.myheader"
  identity_validation_expression = "^123$"
}

resource "aws_api_gateway_authorizer" "request_authorizer" {
  name = "request_authorizer"
  rest_api_id = aws_api_gateway_rest_api.api.id
  authorizer_uri = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.invocation_role.arn
  identity_source = "method.request.header.myheader, method.request.querystring.mystring"
  type = "REQUEST"
}

resource "aws_api_gateway_authorizer" "request_authorizer_empty" {
  name = "request_authorizer"
  rest_api_id = aws_api_gateway_rest_api.api.id
  authorizer_uri = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.invocation_role.arn
  identity_source = ""
  type = "REQUEST"
}

resource "aws_lambda_function" "authorizer" {
  filename = "lambda-functions.zip"
  function_name = "authorizer"
  role = aws_iam_role.invocation_role.arn
  handler = "handlers.auth_handler"
  runtime = "python3.8"
  source_code_hash = filebase64sha256("lambda-functions.zip")
}

resource "aws_lambda_function" "hello_endpoint" {
  filename = "lambda-functions.zip"
  function_name = "hello_lambda"
  role = aws_iam_role.invocation_role.arn
  handler = "handlers.hello_handler"
  runtime = "python3.8"
  source_code_hash = filebase64sha256("lambda-functions.zip")
}

resource "aws_api_gateway_method" "get_hello" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource.id
  http_method = "GET"
  authorizer_id = aws_api_gateway_authorizer.header_authorizer.id
  authorization = "CUSTOM"
}

resource "aws_api_gateway_method" "get_hello_request" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource_request.id
  http_method = "GET"
  authorizer_id = aws_api_gateway_authorizer.request_authorizer.id
  authorization = "CUSTOM"
}

resource "aws_api_gateway_method" "get_hello_request_empty" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource_request_empty.id
  http_method = "GET"
  authorizer_id = aws_api_gateway_authorizer.request_authorizer_empty.id
  authorization = "CUSTOM"
}

resource "aws_api_gateway_resource" "hello_resource" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id = aws_api_gateway_rest_api.api.root_resource_id
  path_part = "hello"
}

resource "aws_api_gateway_resource" "hello_resource_request" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id = aws_api_gateway_rest_api.api.root_resource_id
  path_part = "hello-request"
}

resource "aws_api_gateway_resource" "hello_resource_request_empty" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id = aws_api_gateway_rest_api.api.root_resource_id
  path_part = "hello-request-empty"
}

resource "aws_api_gateway_integration" "MyDemoIntegration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource.id
  http_method = aws_api_gateway_method.get_hello.http_method
  type = "AWS_PROXY"
  content_handling = "CONVERT_TO_TEXT"
  uri = aws_lambda_function.hello_endpoint.invoke_arn
}

resource "aws_api_gateway_integration" "MyDemoIntegrationRequest" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource_request.id
  http_method = aws_api_gateway_method.get_hello_request.http_method
  type = "AWS_PROXY"
  content_handling = "CONVERT_TO_TEXT"
  uri = aws_lambda_function.hello_endpoint.invoke_arn
}

resource "aws_api_gateway_integration" "MyDemoIntegrationRequestEmpty" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource_request_empty.id
  http_method = aws_api_gateway_method.get_hello_request_empty.http_method
  type = "AWS_PROXY"
  content_handling = "CONVERT_TO_TEXT"
  uri = aws_lambda_function.hello_endpoint.invoke_arn
}

resource "aws_api_gateway_rest_api" "api" {
  name = "api"
}

resource "aws_iam_role" "invocation_role" {
  name = "iam_lambda"
  path = "/"
  assume_role_policy = <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Effect": "Allow",
      "Sid": ""
    }
  ]
}
EOF
}