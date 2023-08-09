provider "aws" {}

data "aws_region" "current" {}

resource "random_uuid" "unique_id" {
    keepers = {
        my_key = "my_key"
    }
}

resource "aws_api_gateway_authorizer" "header_authorizer" {
  name = "header-authorizer-open-api_${random_uuid.unique_id.result}"
  rest_api_id = aws_api_gateway_rest_api.api.id
  authorizer_uri = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.invocation_role.arn
  identity_source = "method.request.header.myheader"
  identity_validation_expression = "^123$"
}

resource "aws_lambda_function" "authorizer" {
  filename = "lambda-functions.zip"
  function_name = "authorizer-open-api_${random_uuid.unique_id.result}"
  role = aws_iam_role.invocation_role.arn
  handler = "handlers.auth_handler"
  runtime = "python3.8"
  source_code_hash = filebase64sha256("lambda-functions.zip")
}

resource "aws_lambda_function" "hello_endpoint" {
  filename = "lambda-functions.zip"
  function_name = "hello-lambda-open-api_${random_uuid.unique_id.result}"
  role = aws_iam_role.invocation_role.arn
  handler = "handlers.hello_handler"
  runtime = "python3.8"
  source_code_hash = filebase64sha256("lambda-functions.zip")
}

resource "aws_api_gateway_rest_api" "api" {
  name = "api-open-api_${random_uuid.unique_id.result}"
  body = jsonencode({
    swagger = "2.0"
    info = {
      title = "api-body"
      version = "1.0"
    }
    securityDefinitions = {
      TokenAuthorizer = {
        type = "apiKey"
        in = "header"
        name = "myheader"
        x-amazon-apigateway-authtype = "custom"
        x-amazon-apigateway-authorizer = {
          type = "TOKEN"
          identityValidationExpression = "^123$"
          authorizerUri = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.authorizer.arn}/invocations"
        }
      }
      RequestAuthorizer = {
        type = "apiKey"
        in = "unused"
        name = "unused"
        x-amazon-apigateway-authtype = "custom"
        x-amazon-apigateway-authorizer = {
          type = "REQUEST"
          identitySource = "method.request.header.myheader, method.request.querystring.mystring"
          authorizerUri = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.authorizer.arn}/invocations"
        }
      }
    }
    paths = {
      "/hello" = {
        get = {
          security = [
            {TokenAuthorizer = []}
          ]
          x-amazon-apigateway-integration = {
            httpMethod = "GET"
            payloadFormatVersion = "1.0"
            type = "AWS_PROXY"
            uri = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.hello_endpoint.arn}/invocations"
          }
        }
      }
      "/hello-request" = {
        get = {
          security = [
            {RequestAuthorizer = []}
          ]
          x-amazon-apigateway-integration = {
            httpMethod = "GET"
            payloadFormatVersion = "1.0"
            type = "AWS_PROXY"
            uri = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.hello_endpoint.arn}/invocations"
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
