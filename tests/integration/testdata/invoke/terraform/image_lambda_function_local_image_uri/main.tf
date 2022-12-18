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

resource "aws_lambda_function" "image_lambda" {
        function_name = "image_lambda_function"
        package_type = "Image"
        image_config {
          command = ["main.handler"]
        }
        image_uri = "sam-test-lambdaimage:v1"
        timeout = 500
        role = aws_iam_role.iam_for_lambda.arn
}

# serverless.tf 3rd party module
module "image_lambda2" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "4.6.0"
  create_package = false
  function_name = "image_lambda2"
  image_uri     = "sam-test-lambdaimage:v1"
  timeout = 500
  package_type  = "Image"
  image_config_command = ["main.handler"]
}
