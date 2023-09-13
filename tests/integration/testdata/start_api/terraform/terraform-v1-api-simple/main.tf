provider "aws" {
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

resource "aws_lambda_layer_version" "MyAwesomeLayer" {
  filename            = "HelloWorldFunction.zip"
  layer_name          = "MyAwesomeLayer_${random_uuid.unique_id.result}"
  compatible_runtimes = ["python3.8"]
}

resource "aws_lambda_function" "HelloWorldFunction" {
  s3_bucket     = "lambda-code-bucket-${random_uuid.unique_id.result}"
  s3_key        = "s3_lambda_code_key"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "HelloWorldFunction_${random_uuid.unique_id.result}"
  timeout       = 500
  role          = aws_iam_role.iam_for_lambda.arn
  layers        = [aws_lambda_layer_version.MyAwesomeLayer.arn]
  depends_on = [aws_s3_bucket.lambda_code_bucket, aws_s3_object.s3_lambda_code]
}

resource "aws_lambda_function" "HelloWorldFunction2" {
  s3_bucket     = "lambda-code-bucket-${random_uuid.unique_id.result}"
  s3_key        = "s3_lambda_code_key"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "HelloWorldFunction2_${random_uuid.unique_id.result}"
  timeout       = 500
  role          = aws_iam_role.iam_for_lambda.arn
  layers        = [aws_lambda_layer_version.MyAwesomeLayer.arn]
  depends_on = [aws_s3_bucket.lambda_code_bucket, aws_s3_object.s3_lambda_code]
}

resource "aws_api_gateway_rest_api" "MyDemoAPI" {
  name               = "MyDemoAPI-${random_uuid.unique_id.result}"
  binary_media_types = [ "utf-8" ]
}

resource "aws_api_gateway_resource" "MyDemoResource" {
  rest_api_id = aws_api_gateway_rest_api.MyDemoAPI.id
  parent_id   = aws_api_gateway_rest_api.MyDemoAPI.root_resource_id
  path_part   = "hello"
}

resource "aws_api_gateway_method" "GetMethod" {
  rest_api_id    = aws_api_gateway_rest_api.MyDemoAPI.id
  resource_id    = aws_api_gateway_resource.MyDemoResource.id
  http_method    = "GET"
  authorization  = "NONE"
}

resource "aws_api_gateway_method" "PostMethod" {
  rest_api_id    = aws_api_gateway_rest_api.MyDemoAPI.id
  resource_id    = aws_api_gateway_resource.MyDemoResource.id
  http_method    = "POST"
  authorization  = "NONE"
}

resource "aws_api_gateway_stage" "MyDemoStage" {
  stage_name    = "prod-${random_uuid.unique_id.result}"
  rest_api_id   = aws_api_gateway_rest_api.MyDemoAPI.id
  deployment_id = aws_api_gateway_deployment.MyDemoDeployment.id
}

resource "aws_api_gateway_deployment" "MyDemoDeployment" {
  rest_api_id = aws_api_gateway_rest_api.MyDemoAPI.id
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.MyDemoResource.id,
      aws_api_gateway_method.GetMethod.http_method,
      aws_api_gateway_integration.MyDemoIntegration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_integration" "MyDemoIntegration" {
  rest_api_id      = aws_api_gateway_rest_api.MyDemoAPI.id
  resource_id      = aws_api_gateway_resource.MyDemoResource.id
  http_method      = aws_api_gateway_method.GetMethod.http_method
  integration_http_method = "POST"
  type             = "AWS_PROXY"
  content_handling = "CONVERT_TO_TEXT"
  uri              = aws_lambda_function.HelloWorldFunction.invoke_arn
  depends_on = [aws_api_gateway_method.GetMethod]
}

resource "aws_api_gateway_integration" "MyDemoIntegrationMock" {
  rest_api_id      = aws_api_gateway_rest_api.MyDemoAPI.id
  resource_id      = aws_api_gateway_resource.MyDemoResource.id
  http_method      = aws_api_gateway_method.PostMethod.http_method
  type             = "MOCK"
}
