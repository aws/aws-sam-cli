provider "aws" {
}

resource "aws_iam_role" "iam_for_lambda" {
  name = "iam_for_lambda"

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
  bucket = "lambda_code_bucket"
}

resource "aws_s3_object" "s3_lambda_code" {
    bucket = "lambda_code_bucket"
    key    = "s3_lambda_code_key"
    source = "HelloWorldFunction.zip"
}

resource "aws_lambda_function" "s3_lambda" {
        s3_bucket = "lambda_code_bucket"
        s3_key = "s3_lambda_code_key"
        handler = "app.lambda_handler"
        runtime = "python3.9"
        function_name = "s3_lambda_function"
        timeout = 500
        role = aws_iam_role.iam_for_lambda.arn
