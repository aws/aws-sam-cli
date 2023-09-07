provider "aws" {}

resource "random_uuid" "unique_id" {
    keepers = {
        my_key = "my_key"
    }
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

resource "aws_apigatewayv2_api" "my_api" {
  name           = "my_api"
  protocol_type  = "HTTP"
}

resource "aws_apigatewayv2_integration" "integration" {
  api_id                 = aws_apigatewayv2_api.my_api.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.hello_endpoint.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_hello" {
  api_id         = aws_apigatewayv2_api.my_api.id
  target         = "integrations/${aws_apigatewayv2_integration.integration.id}"
  route_key      = "GET /hello"
  operation_name = "get_hello_operation"
  authorization_type = "CUSTOM"
  authorizer_id = aws_apigatewayv2_authorizer.get_hello.id
}

resource "aws_apigatewayv2_authorizer" "get_hello" {
  api_id           = aws_apigatewayv2_api.my_api.id
  authorizer_type  = "REQUEST"
  authorizer_uri   = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials_arn = aws_iam_role.invocation_role.arn
  authorizer_payload_format_version = "2.0"
  identity_sources = ["$request.header.myheader"]
  name             = "header_authorizer"
}

resource "aws_apigatewayv2_route" "get_hello_request" {
  api_id         = aws_apigatewayv2_api.my_api.id
  target         = "integrations/${aws_apigatewayv2_integration.integration.id}"
  route_key      = "GET /hello-request"
  operation_name = "get_hello_request_operation"
  authorization_type = "CUSTOM"
  authorizer_id = aws_apigatewayv2_authorizer.get_hello_request.id
}

resource "aws_apigatewayv2_authorizer" "get_hello_request" {
  api_id           = aws_apigatewayv2_api.my_api.id
  authorizer_type  = "REQUEST"
  authorizer_uri   = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials_arn = aws_iam_role.invocation_role.arn
  authorizer_payload_format_version = "2.0"
  identity_sources = ["$request.header.myheader", "$request.querystring.mystring"]
  name             = "request_authorizer"
}

resource "aws_apigatewayv2_deployment" "example" {
  api_id      = aws_apigatewayv2_api.my_api.id
  depends_on = [
    aws_apigatewayv2_integration.integration,
    aws_apigatewayv2_route.get_hello,
    aws_apigatewayv2_route.get_hello_request
  ]
}

resource "aws_apigatewayv2_stage" "example" {
  api_id          = aws_apigatewayv2_api.my_api.id
  deployment_id = aws_apigatewayv2_deployment.example.id
  name            = "example-stage-${random_uuid.unique_id.result}"
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