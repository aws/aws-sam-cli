provider "aws" {}

data "aws_region" "current" {}

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
  function_name = "hello-lambda-open-api-${random_uuid.unique_id.result}"
  role = aws_iam_role.invocation_role.arn
  handler = "handlers.hello_handler"
  runtime = "python3.8"
  source_code_hash = filebase64sha256("lambda-functions.zip")
}

resource "aws_apigatewayv2_api" "api" {
  protocol_type = "HTTP"
  name = "api-open-api-${random_uuid.unique_id.result}"
  body = jsonencode({
    "openapi": "3.0",
    "info": {
      "title": "HttpApiOpenApi"
    },
    "components": {
      "securitySchemes": {
        "HeaderAuth": {
          "type": "apiKey",
          "in": "header",
          "name": "notused",
          "x-amazon-apigateway-authorizer": {
            "type": "request",
            "authorizerPayloadFormatVersion": "2.0",
            "identitySource": "$request.header.myheader",
            "authorizerUri": "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.authorizer.arn}/invocations"
          }
        },
        "RequestAuth": {
          "type": "apiKey",
          "in": "header",
          "name": "notused",
          "x-amazon-apigateway-authorizer": {
            "type": "request",
            "authorizerPayloadFormatVersion": "2.0",
            "identitySource": "$request.header.myheader, $request.querystring.mystring",
            "authorizerUri": "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.authorizer.arn}/invocations"
          }
        }
      }
    },
    "paths": {
      "/hello": {
        "get": {
          "security": [
            {
              "HeaderAuth": [

              ]
            }
          ],
          "x-amazon-apigateway-integration": {
            "httpMethod": "POST",
            "type": "AWS_PROXY",
            "uri": "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.hello_endpoint.arn}/invocations"
          }
        }
      },
      "/hello-request": {
        "get": {
          "security": [
            {
              "RequestAuth": [

              ]
            }
          ],
          "x-amazon-apigateway-integration": {
            "httpMethod": "POST",
            "type": "AWS_PROXY",
            "uri": "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.hello_endpoint.arn}/invocations"
          }
        }
      }
    }
  })
}

resource "aws_iam_role" "invocation_role" {
  name = "iam-lambda-open-api_${random_uuid.unique_id.result}"
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
