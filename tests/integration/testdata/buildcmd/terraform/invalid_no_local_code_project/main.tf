provider "aws" {
}

resource "random_pet" "this" {
  length = 2
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

resource "aws_s3_bucket" "lambda_functions_code_bucket" {
  bucket = "simpleapplicationtesting${random_pet.this.id}"
  force_destroy = true
}

resource "aws_lambda_function" "function" {
    s3_bucket = aws_s3_bucket.lambda_functions_code_bucket.id
    s3_key = "s3_lambda_code_key"
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "s3_lambda_function"
    timeout = 500
    role = aws_iam_role.iam_for_lambda.arn
}