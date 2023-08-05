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

resource "aws_apigatewayv2_api" "quick_create_api" {
  name           = "quick_create_api_${random_uuid.unique_id.result}"
  protocol_type  = "HTTP"
  target         = aws_lambda_function.HelloWorldFunction.invoke_arn
  route_key      = "GET /hello"
}
