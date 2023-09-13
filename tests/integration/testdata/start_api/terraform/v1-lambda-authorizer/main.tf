provider "aws" {}

resource "random_uuid" "unique_id" {
    keepers = {
        my_key = "my_key"
    }
}

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

resource "aws_lambda_function" "authorizer" {
  filename = "lambda-functions.zip"
  function_name = "authorizer-${random_uuid.unique_id.result}"
  role = aws_iam_role.invocation_role.arn
  handler = "handlers.auth_handler"
  runtime = "python3.8"
  source_code_hash = filebase64sha256("lambda-functions.zip")
}

resource "aws_lambda_function" "hello_endpoint" {
  filename = "lambda-functions.zip"
  function_name = "hello_lambda-${random_uuid.unique_id.result}"
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

resource "aws_api_gateway_integration" "MyDemoIntegration" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource.id
  http_method = aws_api_gateway_method.get_hello.http_method
  integration_http_method = "POST"
  type = "AWS_PROXY"
  content_handling = "CONVERT_TO_TEXT"
  uri = aws_lambda_function.hello_endpoint.invoke_arn
}

resource "aws_api_gateway_integration" "MyDemoIntegrationRequest" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.hello_resource_request.id
  http_method = aws_api_gateway_method.get_hello_request.http_method
  integration_http_method = "POST"
  type = "AWS_PROXY"
  content_handling = "CONVERT_TO_TEXT"
  uri = aws_lambda_function.hello_endpoint.invoke_arn
}

resource "aws_api_gateway_rest_api" "api" {
  name = "api-${random_uuid.unique_id.result}"
}

resource "aws_iam_role" "invocation_role" {
  name = "iam_lambda-${random_uuid.unique_id.result}"
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