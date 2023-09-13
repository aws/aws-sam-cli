provider "aws" {
}

locals {
    api_function = aws_lambda_function.HelloWorldFunction.invoke_arn
}

resource "random_uuid" "unique_id" {
    keepers = {
        my_key = "my_key"
    }
}

resource "aws_iam_role" "iam_for_lambda" {
  name = "iam_for_lambda_${random_uuid.unique_id.result}"

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

resource "aws_s3_bucket" "lambda_code_bucket" {
  bucket = "lambda-code-bucket-${random_uuid.unique_id.result}"
}

resource "aws_s3_object" "s3_lambda_code" {
  bucket = "lambda-code-bucket-${random_uuid.unique_id.result}"
  key    = "s3_lambda_code_key"
  source = "HelloWorldFunction.zip"
  depends_on = [aws_s3_bucket.lambda_code_bucket]
}

resource "aws_lambda_function" "HelloWorldFunction" {
  s3_bucket     = "lambda-code-bucket-${random_uuid.unique_id.result}"
  s3_key        = "s3_lambda_code_key"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "HelloWorldFunction_${random_uuid.unique_id.result}"
  timeout       = 500
  role          = aws_iam_role.iam_for_lambda.arn
  depends_on = [aws_s3_bucket.lambda_code_bucket]
}

resource "aws_apigatewayv2_api" "my_api" {
  name           = "my_api_${random_uuid.unique_id.result}"
  protocol_type  = "HTTP"
}

resource "aws_apigatewayv2_route" "example" {
  api_id         = aws_apigatewayv2_api.my_api.id
  target         = "integrations/${aws_apigatewayv2_integration.example.id}"
  route_key      = "GET /hello"
  operation_name = "my_operation"
  depends_on = [aws_apigatewayv2_integration.example]
}

resource "aws_apigatewayv2_deployment" "example" {
  api_id      = aws_apigatewayv2_api.my_api.id
  depends_on = [aws_apigatewayv2_integration.example, aws_apigatewayv2_route.example]
}

resource "aws_apigatewayv2_stage" "example" {
  api_id          = aws_apigatewayv2_api.my_api.id
  deployment_id = aws_apigatewayv2_deployment.example.id
  name            = "example-stage-${random_uuid.unique_id.result}"
}

resource "aws_apigatewayv2_integration" "example" {
  api_id                 = aws_apigatewayv2_api.my_api.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = local.api_function
  payload_format_version = "2.0"
}
